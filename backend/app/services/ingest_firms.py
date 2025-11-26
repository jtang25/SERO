import httpx
import csv
from io import StringIO
from datetime import datetime
from sqlalchemy.orm import Session
from ..config import NASA_FIRMS_MAP_KEY
from ..models.firms import FirmsDetection

def parse_acq_ts(date_str: str, time_str: str) -> datetime:
    # date: YYYY-MM-DD, time: HHMM
    dt = datetime.strptime(date_str + time_str, "%Y-%m-%d%H%M")
    return dt.replace(tzinfo=None)  # or timezone-aware if you prefer

async def ingest_firms_once(db: Session):
    # Rough bounding box for PNW / WA; refine later
    bbox = "-125,45,-116,50"
    # 1 = last 24h
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{NASA_FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{bbox}/1"

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        csv_text = resp.text

    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        acq_ts = parse_acq_ts(row["acq_date"], row["acq_time"])

        # You may want to dedup by (lat, lon, acq_ts)
        det = FirmsDetection(
            src="VIIRS_SNPP_NRT",
            acq_time=acq_ts,
            latitude=lat,
            longitude=lon,
            brightness=float(row.get("bright_ti4") or 0.0),
            confidence=row.get("confidence"),
            frp=float(row.get("frp") or 0.0),
        )
        db.add(det)

    db.commit()
