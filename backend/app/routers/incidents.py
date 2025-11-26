# app/routers/incidents.py

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.fire_incidents import FireIncident
from ..models.police_calls import PoliceCall
from ..services.ingest_fire import ingest_fire_once
from ..services.ingest_police import ingest_police_once
from ..services.aggregate_incidents import aggregate_recent_incidents

router = APIRouter()


# --- Fire incidents --- #

@router.post("/fire/ingest")
async def ingest_fire(db: Session = Depends(get_db)):
    """
    One-off dev endpoint to pull the latest Seattle Fire 911 calls
    into the Supabase database.
    """
    await ingest_fire_once(db)
    return {"status": "ok"}


@router.get("/fire/recent")
def get_recent_fire(
    limit: int = 100,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """
    Return recent fire incidents from the last `hours` hours,
    up to `limit` rows.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    q = (
        db.query(FireIncident)
        .filter(FireIncident.ts >= since)
        .order_by(FireIncident.ts.desc())
        .limit(limit)
    )

    items = []
    for inc in q.all():
        items.append(
            {
                "incident_number": inc.incident_number,
                "call_type": inc.call_type,
                "call_description": inc.call_description,
                "priority": inc.priority,
                "ts": inc.ts.isoformat() if inc.ts else None,
                "address": inc.address,
                "latitude": inc.latitude,
                "longitude": inc.longitude,
            }
        )

    return {"items": items}


# --- Police calls --- #

@router.post("/police/ingest")
async def ingest_police(db: Session = Depends(get_db)):
    """
    One-off dev endpoint to pull the latest Seattle Police call data
    into the Supabase database.
    """
    await ingest_police_once(db)
    return {"status": "ok"}


@router.get("/police/recent")
def get_recent_police(
    limit: int = 100,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """
    Return recent police calls from the last `hours` hours,
    up to `limit` rows.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    q = (
        db.query(PoliceCall)
        .filter(PoliceCall.ts >= since)
        .order_by(PoliceCall.ts.desc())
        .limit(limit)
    )

    items = []
    for call in q.all():
        items.append(
            {
                "cad_event_number": call.cad_event_number,
                "initial_call_type": call.initial_call_type,
                "final_call_type": call.final_call_type,
                "priority": call.priority,
                "ts": call.ts.isoformat() if call.ts else None,
                "beat": call.beat,
                "latitude": call.latitude,
                "longitude": call.longitude,
            }
        )

    return {"items": items}

@router.post("/aggregate_counts")
def aggregate_counts(
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """
    Aggregate raw fire_incidents and police_calls into incident_counts
    for the last `hours` hours.

    This is a dev/manual endpoint. In a real deployment, you'd call this
    periodically from a scheduler / cron.
    """
    buckets_updated = aggregate_recent_incidents(db, hours=hours)
    return {
        "status": "ok",
        "hours": hours,
        "buckets_updated": buckets_updated,
    }
