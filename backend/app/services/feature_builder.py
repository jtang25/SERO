import numpy as np
import pandas as pd
from datetime import timedelta
from sqlalchemy.orm import Session
from ..models.incident_counts import IncidentCount

class FeatureBuilder:
    def __init__(self, grid_indexer, horizon_hours: int = 3):
        self.grid = grid_indexer
        self.H = horizon_hours

    def _time_features(self, ts):
        hour = ts.hour
        dow = ts.weekday()
        return {
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "dow_sin": np.sin(2 * np.pi * dow / 7),
            "dow_cos": np.cos(2 * np.pi * dow / 7),
            "is_weekend": int(dow >= 5),
            "is_night": int(hour < 6 or hour >= 22),
        }

    def _history_features_for_cell(self, db: Session, cell_id: int, ts):
        # Example: counts from incident_counts table
        # [ts-1h, ts), [ts-3h, ts), [ts-24h, ts)
        def sum_range(hours):
            start = ts - timedelta(hours=hours)
            rows = (
                db.query(IncidentCount)
                .filter(
                    IncidentCount.cell_id == cell_id,
                    IncidentCount.bucket_start >= start,
                    IncidentCount.bucket_start < ts,
                )
                .all()
            )
            fire = sum(r.fire_count for r in rows)
            police = sum(r.police_count for r in rows)
            return fire, police

        f1, p1 = sum_range(1)
        f3, p3 = sum_range(3)
        f24, p24 = sum_range(24)

        return {
            "fire_last_1h": f1,
            "fire_last_3h": f3,
            "fire_last_24h": f24,
            "police_last_1h": p1,
            "police_last_3h": p3,
            "police_last_24h": p24,
        }

    def build_snapshot_features(self, db: Session, ts):
        rows = []
        time_feats = self._time_features(ts)
        n_cells = self.grid.n_lat * self.grid.n_lon

        for cell_id in range(n_cells):
            hist_feats = self._history_features_for_cell(db, cell_id, ts)
            rows.append({"cell_id": cell_id, **time_feats, **hist_feats})

        return pd.DataFrame(rows)
