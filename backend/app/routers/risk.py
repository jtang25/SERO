# app/routers/risk.py
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text
import joblib

from app.db import engine
from app.services.grid_indexer import GridIndexer

router = APIRouter()

# -------------------------------------------------------------------
# Model paths
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]   # .../backend
MODELS_DIR = BASE_DIR / "app" / "models"

CLF_PATH     = MODELS_DIR / "risk_xgb.pkl"
REG_PATH     = MODELS_DIR / "risk_xgb_total.pkl"
IMPUTER_PATH = MODELS_DIR / "risk_imputer.pkl"

try:
    clf = joblib.load(CLF_PATH)
    reg = joblib.load(REG_PATH)
    imputer = joblib.load(IMPUTER_PATH)
    print(
        f"[Risk] Loaded models: clf={CLF_PATH.name}, "
        f"reg={REG_PATH.name}, imputer={IMPUTER_PATH.name}, "
        f"n_features={imputer.n_features_in_}"
    )
except Exception as e:
    print(f"[Risk] WARNING: could not load risk models: {e}")
    clf = None
    reg = None
    imputer = None

# -------------------------------------------------------------------
# Feature config  (MUST match training notebook)
# -------------------------------------------------------------------
history_cols = [
    "fire_last_1h", "fire_last_3h", "fire_last_24h",
    "police_last_1h", "police_last_3h", "police_last_24h",
]

time_cols = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "is_weekend", "is_night",
]

# Include cell_id as numeric feature (assuming training did this too)
id_cols = ["cell_id"]

feature_cols = history_cols + time_cols + id_cols
BASE_THRESHOLD = 0.8

# Grid indexer for computing centroids purely from cell_id
grid_indexer = GridIndexer(
    47.48, 47.75,        # min_lat, max_lat
    -122.45, -122.22,    # min_lon, max_lon
    0.01, 0.01           # lat_step, lon_step
)


class RiskCell(BaseModel):
    cell_id: int
    bucket_start: str
    risk_score: float
    high_risk: bool
    expected_incidents: float

    fire_last_1h: float
    fire_last_3h: float
    fire_last_24h: float
    police_last_1h: float
    police_last_3h: float
    police_last_24h: float

    lat: Optional[float] = None
    lon: Optional[float] = None


def _ensure_models_loaded():
    if clf is None or reg is None or imputer is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Risk model not loaded; train and save "
                "risk_xgb.pkl, risk_xgb_total.pkl, and risk_imputer.pkl "
                "under app/models."
            ),
        )


def get_risk_grid() -> dict:
    """
    Compute risk grid for the latest hour.

    Returns:
        {
          "timestamp": <ISO timestamp string>,
          "cells": [ { ... per cell dict ... }, ... ]
        }
    """
    _ensure_models_loaded()

    # ------------------------------------------------------------------
    # 1) Pull latest timestamp and last 24h of incident_counts
    # ------------------------------------------------------------------
    with engine.connect() as conn:
        latest_ts = conn.execute(
            text("SELECT MAX(bucket_start) AS ts FROM incident_counts")
        ).scalar()

        if latest_ts is None:
            raise HTTPException(status_code=404, detail="No incident_counts data")

        start_ts = latest_ts - timedelta(hours=24)

        df_counts = pd.read_sql(
            text("""
                SELECT cell_id, bucket_start, fire_count, police_count
                FROM incident_counts
                WHERE bucket_start BETWEEN :start_ts AND :end_ts
            """),
            conn,
            params={"start_ts": start_ts, "end_ts": latest_ts},
            parse_dates=["bucket_start"],
        )

    if df_counts.empty:
        raise HTTPException(status_code=404, detail="No incident_counts in last 24h")

    # ------------------------------------------------------------------
    # 2) Densify: all cells seen in incident_counts x all hours
    # ------------------------------------------------------------------
    cells = df_counts["cell_id"].unique()

    tz = df_counts["bucket_start"].dt.tz
    all_hours = pd.date_range(start_ts, latest_ts, freq="H", tz=tz)

    full_index = pd.MultiIndex.from_product(
        [cells, all_hours],
        names=["cell_id", "bucket_start"],
    )

    df = (
        df_counts
        .set_index(["cell_id", "bucket_start"])
        .reindex(full_index)
        .fillna({"fire_count": 0, "police_count": 0})
        .reset_index()
    )

    # ------------------------------------------------------------------
    # 3) Recompute history features per cell
    # ------------------------------------------------------------------
    g = df.groupby("cell_id", group_keys=False)

    df["fire_last_1h"]  = g["fire_count"].apply(
        lambda s: s.shift(1).rolling(1,  min_periods=1).sum()
    )
    df["fire_last_3h"]  = g["fire_count"].apply(
        lambda s: s.shift(1).rolling(3,  min_periods=1).sum()
    )
    df["fire_last_24h"] = g["fire_count"].apply(
        lambda s: s.shift(1).rolling(24, min_periods=1).sum()
    )

    df["police_last_1h"]  = g["police_count"].apply(
        lambda s: s.shift(1).rolling(1,  min_periods=1).sum()
    )
    df["police_last_3h"]  = g["police_count"].apply(
        lambda s: s.shift(1).rolling(3,  min_periods=1).sum()
    )
    df["police_last_24h"] = g["police_count"].apply(
        lambda s: s.shift(1).rolling(24, min_periods=1).sum()
    )

    df[history_cols] = df[history_cols].fillna(0)

    # ------------------------------------------------------------------
    # 4) Keep only rows at the latest timestamp (df_latest)
    # ------------------------------------------------------------------
    df_latest = df[df["bucket_start"] == latest_ts].copy()
    if df_latest.empty:
        raise HTTPException(
            status_code=500,
            detail="No rows for latest bucket_start after feature building",
        )

    # ------------------------------------------------------------------
    # 5) Time features for that timestamp
    # ------------------------------------------------------------------
    df_latest["hour"] = df_latest["bucket_start"].dt.hour
    df_latest["dow"]  = df_latest["bucket_start"].dt.dayofweek  # Monday=0

    df_latest["hour_sin"] = np.sin(2 * np.pi * df_latest["hour"] / 24)
    df_latest["hour_cos"] = np.cos(2 * np.pi * df_latest["hour"] / 24)
    df_latest["dow_sin"]  = np.sin(2 * np.pi * df_latest["dow"] / 7)
    df_latest["dow_cos"]  = np.cos(2 * np.pi * df_latest["dow"] / 7)

    df_latest["is_weekend"] = (df_latest["dow"] >= 5).astype(int)
    df_latest["is_night"]   = (
        (df_latest["hour"] < 6) | (df_latest["hour"] >= 22)
    ).astype(int)

    # ------------------------------------------------------------------
    # 6) Run through imputer + models (including cell_id in features)
    # ------------------------------------------------------------------
    missing = [c for c in feature_cols if c not in df_latest.columns]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing feature columns in df_latest: {missing}",
        )

    X = df_latest[feature_cols].to_numpy()

    # Safety check
    if imputer.n_features_in_ != X.shape[1]:
        print(
            f"[Risk] Feature mismatch: imputer expects {imputer.n_features_in_}, "
            f"but X has {X.shape[1]} columns."
        )

    X_imp = imputer.transform(X)
    scores = clf.predict_proba(X_imp)[:, 1]
    expected = np.clip(reg.predict(X_imp), a_min=0.0, a_max=None)

    df_latest["risk_score"] = scores
    df_latest["expected_incidents"] = expected
    df_latest["high_risk"] = df_latest["risk_score"] >= BASE_THRESHOLD

    # ------------------------------------------------------------------
    # 7) Pack response, computing lat/lon purely from GridIndexer
    # ------------------------------------------------------------------
    cells_out = []
    for row in df_latest.itertuples():
        lat_val, lon_val = grid_indexer.cell_to_centroid(int(row.cell_id))

        cells_out.append(
            {
                "cell_id": int(row.cell_id),
                "bucket_start": row.bucket_start.isoformat(),
                "risk_score": float(row.risk_score),
                "high_risk": bool(row.high_risk),
                "expected_incidents": float(row.expected_incidents),
                "fire_last_1h": float(row.fire_last_1h),
                "fire_last_3h": float(row.fire_last_3h),
                "fire_last_24h": float(row.fire_last_24h),
                "police_last_1h": float(row.police_last_1h),
                "police_last_3h": float(row.police_last_3h),
                "police_last_24h": float(row.police_last_24h),
                "lat": float(lat_val),
                "lon": float(lon_val),
            }
        )

    return {
        "timestamp": latest_ts.isoformat(),
        "cells": cells_out,
    }


@router.get("/latest", response_model=List[RiskCell])
def get_latest_risk():
    """HTTP endpoint that wraps get_risk_grid() and returns a list of RiskCell."""
    snapshot = get_risk_grid()
    return [RiskCell(**cell) for cell in snapshot["cells"]]
