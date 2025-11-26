# app/services/aggregate_incidents.py

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.fire_incidents import FireIncident
from ..models.police_calls import PoliceCall
from ..models.incident_counts import IncidentCount
from .grid_indexer import GridIndexer


# Define the grid you want to use for Seattle.
# Make sure these bounds and resolutions match what you use elsewhere.
GRID = GridIndexer(
    min_lat=47.48,
    max_lat=47.75,
    min_lon=-122.45,
    max_lon=-122.22,
    dlat=0.01,
    dlon=0.01,
)


def floor_to_hour(ts: datetime) -> datetime:
    """
    Truncate a datetime to the start of the hour, preserving timezone info.
    """
    return ts.replace(minute=0, second=0, microsecond=0)


def _compute_and_trim_to_first_both(db: Session) -> Optional[datetime]:
    """
    Find the earliest bucket_start in incident_counts such that
    SUM(fire_count) > 0 AND SUM(police_count) > 0 across all cells,
    and delete all rows earlier than that bucket_start.

    Returns the cutoff timestamp (the first hour with both fire & police),
    or None if no such hour exists yet.
    """

    # Aggregate per hour across all cells
    rows = (
        db.query(
            IncidentCount.bucket_start.label("bucket_start"),
            func.sum(IncidentCount.fire_count).label("fire_total"),
            func.sum(IncidentCount.police_count).label("police_total"),
        )
        .groupby(IncidentCount.bucket_start)
        .order_by(IncidentCount.bucket_start)
        .all()
    )

    cutoff: Optional[datetime] = None
    for r in rows:
        if (r.fire_total or 0) > 0 and (r.police_total or 0) > 0:
            cutoff = r.bucket_start
            break

    if cutoff is None:
        # No overlapping hour yet; nothing to trim
        return None

    # Delete all rows before that cutoff
    (
        db.query(IncidentCount)
        .filter(IncidentCount.bucket_start < cutoff)
        .delete(synchronize_session=False)
    )

    return cutoff


def aggregate_incident_counts_range(
    db: Session,
    start: datetime,
    end: datetime,
) -> int:
    """
    Aggregate fire_incidents and police_calls into incident_counts
    for all incidents with ts in [start, end).

    For each (cell_id, bucket_start) we recompute exact counts and
    overwrite fire_count / police_count. After aggregating, we also
    trim incident_counts so that it starts at the first hour where
    BOTH fire and police have at least one incident (anywhere in the grid).

    Returns the number of (cell_id, bucket_start) buckets updated.
    """

    # Key: (cell_id, bucket_start), Value: {"fire": int, "police": int}
    counts: Dict[Tuple[int, datetime], Dict[str, int]] = defaultdict(
        lambda: {"fire": 0, "police": 0}
    )

    # --- Aggregate FireIncident --- #

    fire_q = (
        db.query(FireIncident)
        .filter(FireIncident.ts >= start, FireIncident.ts < end)
        .filter(FireIncident.latitude.isnot(None), FireIncident.longitude.isnot(None))
    )

    for inc in fire_q.all():
        cell_id = GRID.latlon_to_cell(inc.latitude, inc.longitude)
        if cell_id is None:
            continue

        bucket_start = floor_to_hour(inc.ts)
        key = (cell_id, bucket_start)
        counts[key]["fire"] += 1

    # --- Aggregate PoliceCall --- #

    police_q = (
        db.query(PoliceCall)
        .filter(PoliceCall.ts >= start, PoliceCall.ts < end)
        .filter(PoliceCall.latitude.isnot(None), PoliceCall.longitude.isnot(None))
    )

    for call in police_q.all():
        cell_id = GRID.latlon_to_cell(call.latitude, call.longitude)
        if cell_id is None:
            continue

        bucket_start = floor_to_hour(call.ts)
        key = (cell_id, bucket_start)
        counts[key]["police"] += 1

    # --- Upsert into incident_counts --- #

    for (cell_id, bucket_start), c in counts.items():
        fire_count = c["fire"]
        police_count = c["police"]

        existing = (
            db.query(IncidentCount)
            .filter(
                IncidentCount.cell_id == cell_id,
                IncidentCount.bucket_start == bucket_start,
            )
            .one_or_none()
        )

        if existing:
            existing.fire_count = fire_count
            existing.police_count = police_count
        else:
            row = IncidentCount(
                cell_id=cell_id,
                bucket_start=bucket_start,
                fire_count=fire_count,
                police_count=police_count,
            )
            db.add(row)

    # After upserting, trim to the first hour where both fire & police > 0
    cutoff = _compute_and_trim_to_first_both(db)

    # Final commit for both upserts and trimming
    db.commit()

    return len(counts)


def aggregate_recent_incidents(db: Session, hours: int = 24) -> int:
    """
    Convenience wrapper: aggregate incidents for the last `hours`,
    aligned to whole hours in UTC, and then trim the table so that it
    starts at the first hour with both fire & police present.
    """
    end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    return aggregate_incident_counts_range(db, start, end)
