# app/llm/risk_model.py
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import logging

log = logging.getLogger(__name__)

# These must match your training notebook
history_cols = [
    "fire_last_1h", "fire_last_3h", "fire_last_24h",
    "police_last_1h", "police_last_3h", "police_last_24h",
]

time_cols = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "is_weekend", "is_night",
]

feature_cols = history_cols + time_cols


class RiskModel:
    """
    Wraps BOTH:
      - classifier: P(incident > 0)
      - regressor: E[future_total]
    plus the imputer.

    The orchestrator still instantiates with:
        RiskModel("app/models/risk_model.pkl")

    Internally we also look for:
        app/models/risk_xgb.pkl
        app/models/risk_xgb_total.pkl
        app/models/risk_imputer.pkl
    in the same directory.
    """

    def __init__(self, model_path: str):
        base = Path(model_path)

        self.classifier: Optional[object] = None
        self.regressor: Optional[object] = None
        self.imputer: Optional[object] = None

        # ------------------ classifier ------------------
        # Prefer explicit risk_model.pkl if it exists
        clf_paths = [base, base.with_name("risk_xgb.pkl")]
        clf_loaded = False
        for p in clf_paths:
            if p.exists():
                self.classifier = joblib.load(p)
                log.info("[RiskModel] Loaded classifier from %s", p)
                clf_loaded = True
                break

        if not clf_loaded:
            log.warning(
                "[RiskModel] WARNING: risk model file not found at %s or %s. "
                "Risk outputs will be zeros until you train and save the model.",
                clf_paths[0],
                clf_paths[1],
            )

        # ------------------ regressor -------------------
        reg_path = base.with_name("risk_xgb_total.pkl")
        if reg_path.exists():
            self.regressor = joblib.load(reg_path)
            log.info("[RiskModel] Loaded expected-incidents regressor from %s", reg_path)
        else:
            log.warning(
                "[RiskModel] WARNING: expected-incidents model file not found at %s. "
                "expected_incidents will default to 0.",
                reg_path,
            )

        # ------------------ imputer ---------------------
        imp_path = base.with_name("risk_imputer.pkl")
        if imp_path.exists():
            self.imputer = joblib.load(imp_path)
            log.info("[RiskModel] Loaded imputer from %s", imp_path)
        else:
            log.warning(
                "[RiskModel] WARNING: imputer file not found at %s. "
                "Features will be used as-is.",
                imp_path,
            )

    # ------------------ internal helpers ------------------

    def _prepare_features(self, df):
        """Selects feature columns and applies imputer (same as training)."""
        X = df[feature_cols].to_numpy()
        if self.imputer is not None:
            X = self.imputer.transform(X)
        return X

    # ------------------ public API ------------------

    def predict_proba(self, df) -> np.ndarray:
        """
        Returns probability of label=1 (incident occurs) for each row.
        Shape: (n_samples,)
        """
        n = len(df)
        if self.classifier is None:
            return np.zeros(n, dtype=float)

        X = self._prepare_features(df)
        proba = self.classifier.predict_proba(X)[:, 1]
        return proba

    def predict_expected(self, df) -> np.ndarray:
        """
        Returns E[future_total] (expected number of incidents) for each row.
        Shape: (n_samples,)
        """
        n = len(df)
        if self.regressor is None:
            return np.zeros(n, dtype=float)

        X = self._prepare_features(df)
        y_hat = self.regressor.predict(X)
        # no negative incident counts
        return np.clip(y_hat, a_min=0.0, a_max=None)
