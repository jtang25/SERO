# app/services/ingest_fire.py

from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..models.fire_incidents import FireIncident

# Seattle Real Time Fire 911 Calls
# Schema (from official CSV):
# "address","type","datetime","latitude","longitude","report_location","incident_number"
FIRE_API_URL = "https://data.seattle.gov/resource/kzjm-xkqj.json"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Parse timestamps like '2025-09-24T13:39:00.000' (with optional 'Z').
    """
    if not value:
        return None
    try:
        value = value.rstrip("Z")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def ingest_fire_once(db: Session) -> int:
    """
    Pull recent Seattle Fire 911 calls into fire_incidents.

    Idempotent on incident_number:
    - Preloads existing incident_numbers.
    - Skips any row whose incident_number already exists.
    """

    params = {
        "$limit": 100000,
        "$order": "datetime DESC", 
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(FIRE_API_URL, params=params)

    resp.raise_for_status()
    rows = resp.json()

    # Preload existing incident_numbers so we don't duplicate
    existing_ids = {
        row[0]
        for row in db.query(FireIncident.incident_number).all()
        if row[0] is not None
    }

    inserted = 0
    skipped = 0

    for row in rows:
        incident_number = row.get("incident_number")
        if not incident_number:
            continue

        if incident_number in existing_ids:
            skipped += 1
            continue

        ts = _parse_dt(row.get("datetime"))

        # address, type, datetime, latitude, longitude, report_location, incident_number
        address = row.get("address")
        call_type = row.get("type")
        call_description = call_type

        lat = _parse_float(row.get("latitude"))
        lon = _parse_float(row.get("longitude"))

        inc = FireIncident(
            incident_number=incident_number,
            call_type=call_type,
            call_description=call_description,
            priority=None,
            ts=ts,
            address=address,
            latitude=lat,
            longitude=lon,
        )
        db.add(inc)

        existing_ids.add(incident_number)
        inserted += 1

    db.commit()

    print(
        f"[ingest_fire] Inserted {inserted} new fire incidents, "
        f"skipped {skipped} existing incident_numbers."
    )
    return inserted
