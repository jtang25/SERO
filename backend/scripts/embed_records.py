import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import text
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.config import OPENAI_API_KEY  # noqa: E402
from app.db import SessionLocal  # noqa: E402


EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
client = OpenAI(api_key=OPENAI_API_KEY)


def vector_to_sql(embedding: Iterable[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def embed_texts(texts: List[str]) -> List[List[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in resp.data]


def coalesce(val, fallback: str) -> str:
    if val is None:
        return fallback
    if isinstance(val, str) and not val.strip():
        return fallback
    return str(val)


def format_fire_incident(row) -> str:
    return (
        f"Fire incident {row.incident_number} at {coalesce(row.address, 'unknown address')}. "
        f"Type: {coalesce(row.call_type, 'unknown')}. "
        f"Description: {coalesce(row.call_description, 'none')}. "
        f"Priority: {coalesce(row.priority, 'unknown')}. "
        f"Occurred: {row.ts.isoformat() if row.ts else 'unknown time'}."
    )


def format_police_call(row) -> str:
    return (
        f"Police call {row.cad_event_number} in beat {coalesce(row.beat, 'unknown')}. "
        f"Initial type: {coalesce(row.initial_call_type, 'unknown')}. "
        f"Final type: {coalesce(row.final_call_type, 'unknown')}. "
        f"Priority: {coalesce(row.priority, 'unknown')}. "
        f"Occurred: {row.ts.isoformat() if row.ts else 'unknown time'}."
    )


def risk_level_from_totals(fire_total: int, police_total: int) -> str:
    total = fire_total + police_total
    if total >= 150:
        return "high"
    if total >= 60:
        return "medium"
    return "low"


def format_cell_summary(row) -> str:
    risk_level = risk_level_from_totals(row.fire_total, row.police_total)
    window_start = row.window_start.isoformat() if row.window_start else "unknown"
    window_end = row.window_end.isoformat() if row.window_end else "unknown"
    return (
        f"Grid cell {row.cell_id} has had {row.fire_total} fire incidents and "
        f"{row.police_total} police incidents between {window_start} and {window_end}. "
        f"Overall risk level: {risk_level}."
    )


def embed_fire_incidents(db, limit: int, batch_size: int) -> int:
    rows = db.execute(
        text(
            """
            select f.id as incident_id,
                   f.incident_number,
                   f.call_type,
                   f.call_description,
                   f.priority,
                   f.ts,
                   f.address,
                   f.latitude,
                   f.longitude
            from fire_incidents f
            left join fire_incident_embeddings e
              on e.incident_id = f.id
            where e.incident_id is null
            order by f.ts desc
            limit :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    if not rows:
        return 0

    insert_sql = text(
        """
        insert into fire_incident_embeddings (
          incident_id, incident_number, call_type, call_description, priority,
          ts, address, latitude, longitude, content, embedding
        )
        values (
          :incident_id, :incident_number, :call_type, :call_description, :priority,
          :ts, :address, :latitude, :longitude, :content, CAST(:embedding AS vector)
        )
        on conflict (incident_id) do nothing
        """
    )

    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        contents = [format_fire_incident(row) for row in batch]
        embeddings = embed_texts(contents)

        for row, content, embedding in zip(batch, contents, embeddings):
            db.execute(
                insert_sql,
                {
                    **row,
                    "content": content,
                    "embedding": vector_to_sql(embedding),
                },
            )
            inserted += 1
        db.commit()

    return inserted


def embed_police_calls(db, limit: int, batch_size: int) -> int:
    rows = db.execute(
        text(
            """
            select p.id as call_id,
                   p.cad_event_number,
                   p.initial_call_type,
                   p.final_call_type,
                   p.priority,
                   p.ts,
                   p.beat,
                   p.latitude,
                   p.longitude
            from police_calls p
            left join police_call_embeddings e
              on e.call_id = p.id
            where e.call_id is null
            order by p.ts desc
            limit :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    if not rows:
        return 0

    insert_sql = text(
        """
        insert into police_call_embeddings (
          call_id, cad_event_number, initial_call_type, final_call_type, priority,
          ts, beat, latitude, longitude, content, embedding
        )
        values (
          :call_id, :cad_event_number, :initial_call_type, :final_call_type, :priority,
          :ts, :beat, :latitude, :longitude, :content, CAST(:embedding AS vector)
        )
        on conflict (call_id) do nothing
        """
    )

    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        contents = [format_police_call(row) for row in batch]
        embeddings = embed_texts(contents)

        for row, content, embedding in zip(batch, contents, embeddings):
            db.execute(
                insert_sql,
                {
                    **row,
                    "content": content,
                    "embedding": vector_to_sql(embedding),
                },
            )
            inserted += 1
        db.commit()

    return inserted


def embed_cell_summaries(db, limit: int, batch_size: int) -> int:
    rows = db.execute(
        text(
            """
            select agg.cell_id,
                   agg.window_start,
                   agg.window_end,
                   agg.fire_total,
                   agg.police_total
            from (
              select cell_id,
                     min(bucket_start) as window_start,
                     max(bucket_start) as window_end,
                     sum(fire_count) as fire_total,
                     sum(police_count) as police_total
              from incident_counts
              group by cell_id
            ) agg
            left join cell_summary_embeddings e
              on e.cell_id = agg.cell_id
            where e.cell_id is null
            order by agg.cell_id
            limit :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    if not rows:
        return 0

    insert_sql = text(
        """
        insert into cell_summary_embeddings (
          cell_id, window_start, window_end, fire_total, police_total, risk_level,
          content, embedding
        )
        values (
          :cell_id, :window_start, :window_end, :fire_total, :police_total, :risk_level,
          :content, CAST(:embedding AS vector)
        )
        on conflict (cell_id) do nothing
        """
    )

    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        contents = [format_cell_summary(row) for row in batch]
        embeddings = embed_texts(contents)

        for row, content, embedding in zip(batch, contents, embeddings):
            db.execute(
                insert_sql,
                {
                    **row,
                    "risk_level": risk_level_from_totals(
                        int(row.fire_total or 0),
                        int(row.police_total or 0),
                    ),
                    "content": content,
                    "embedding": vector_to_sql(embedding),
                },
            )
            inserted += 1
        db.commit()

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed SERO records into pgvector tables.")
    parser.add_argument(
        "--target",
        choices=["fire", "police", "cells", "all"],
        default="all",
        help="Which data to embed.",
    )
    parser.add_argument("--limit", type=int, default=2000, help="Max rows per target.")
    parser.add_argument("--batch-size", type=int, default=100, help="Embedding batch size.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        total = 0
        if args.target in ("fire", "all"):
            total += embed_fire_incidents(db, args.limit, args.batch_size)
        if args.target in ("police", "all"):
            total += embed_police_calls(db, args.limit, args.batch_size)
        if args.target in ("cells", "all"):
            total += embed_cell_summaries(db, args.limit, args.batch_size)

        print(f"Embedded {total} records using model {EMBED_MODEL}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
