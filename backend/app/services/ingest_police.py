# app/services/ingest_police.py

from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..models.police_calls import PoliceCall

# Seattle SPD "Call Data" dataset
BASE_URL = "https://data.seattle.gov/resource/33kz-ixgy.json"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO-ish timestamps like '2011-05-29T15:32:08.000'.
    Return None if missing/invalid.
    """
    if not value:
        return None
    try:
        value = value.rstrip("Z")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """
    Safely parse floats, ignoring values like 'REDACTED'.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def ingest_police_once(db: Session) -> int:
    """
    Pull recent Seattle SPD call data into the police_calls table.

    Idempotent w.r.t. cad_event_number:
    - Preloads all existing cad_event_number values.
    - Skips any row whose cad_event_number is already present
      (either from previous runs or duplicates in this batch).
    """

    params = {
        "$limit": 100000,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(BASE_URL, params=params)

    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(
            "[ingest_police] HTTP error",
            e.response.status_code,
            e.response.text,
        )
        raise

    rows = resp.json()

    existing_ids = {
        row[0]
        for row in db.query(PoliceCall.cad_event_number).all()
        if row[0] is not None
    }

    inserted = 0
    skipped_existing = 0

    for row in rows:
        cad_event_number = row.get("cad_event_number")
        if not cad_event_number:
            continue

        if cad_event_number in existing_ids:
            skipped_existing += 1
            continue

        ts = _parse_dt(row.get("cad_event_original_time_queued"))

        latitude = _parse_float(row.get("dispatch_latitude"))
        longitude = _parse_float(row.get("dispatch_longitude"))

        call = PoliceCall(
            cad_event_number=cad_event_number,
            initial_call_type=row.get("initial_call_type"),
            final_call_type=row.get("final_call_type"),
            priority=row.get("priority"),
            ts=ts,
            beat=row.get("dispatch_beat"),
            latitude=latitude,
            longitude=longitude,
        )
        db.add(call)

        existing_ids.add(cad_event_number)
        inserted += 1

    db.commit()

    print(
        f"[ingest_police] Inserted {inserted} new SPD calls, "
        f"skipped {skipped_existing} already-existing cad_event_number values."
    )
    return inserted
