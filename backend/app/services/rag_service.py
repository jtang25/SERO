import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import OPENAI_API_KEY
from ..routers import risk as risk_router


EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

DEFAULT_TOP_K = 5
MAX_HISTORY = 8

client = OpenAI(api_key=OPENAI_API_KEY)

FIRE_KEYWORDS = [
    "fire",
    "smoke",
    "alarm",
    "medic",
    "aid",
    "rescue",
    "medical",
]

POLICE_KEYWORDS = [
    "police",
    "crime",
    "assault",
    "burglary",
    "theft",
    "robbery",
    "beat",
    "arrest",
]

CELL_KEYWORDS = [
    "cell",
    "grid",
    "area",
    "zone",
    "risk",
    "hotspot",
    "hot spot",
    "this cell",
    "this area",
    "red",
]

FIRE_ID_RE = re.compile(r"\bF\d{6,}\b", re.IGNORECASE)
POLICE_ID_RE = re.compile(r"\b(?:CAD)?\d{6,}\b", re.IGNORECASE)


def vector_to_sql(embedding: Iterable[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def embed_query(text_value: str) -> List[float]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=[text_value])
    return resp.data[0].embedding


def infer_targets(message: str, view_state: Dict[str, Any]) -> List[str]:
    m = message.lower()
    targets = set()

    if any(k in m for k in FIRE_KEYWORDS):
        targets.add("fire")
    if any(k in m for k in POLICE_KEYWORDS):
        targets.add("police")
    if any(k in m for k in CELL_KEYWORDS):
        targets.add("cells")

    if view_state.get("selected_cell_id") is not None:
        targets.add("cells")
    if view_state.get("focused_cell_id") is not None:
        targets.add("cells")

    if not targets:
        targets = {"fire", "police", "cells"}

    return sorted(targets)


def normalize_view_state(view_state: Dict[str, Any]) -> Dict[str, Any]:
    allowed_keys = {
        "map",
        "focused_cell_id",
        "selected_cell_id",
        "selected_station",
        "selected_trip",
        "deployment",
    }
    return {k: view_state.get(k) for k in allowed_keys if k in view_state}


def should_include_risk(message: str, view_state: Dict[str, Any]) -> bool:
    m = message.lower()
    if any(k in m for k in ["risk", "hotspot", "hot spot", "high risk"]):
        return True
    if view_state.get("selected_cell_id") is not None:
        return True
    if view_state.get("focused_cell_id") is not None:
        return True
    return False


def keyword_search_fire(db: Session, message: str, limit: int) -> List[Dict[str, Any]]:
    ids = FIRE_ID_RE.findall(message)
    if not ids:
        return []
    try:
        rows = db.execute(
            text(
                """
                select incident_id, incident_number, call_type, call_description, priority,
                       ts, address, latitude, longitude, content,
                       1.0 as similarity
                from fire_incident_embeddings
                where incident_number = any(:ids)
                order by ts desc
                limit :limit
                """
            ),
            {"ids": ids, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def keyword_search_police(db: Session, message: str, limit: int) -> List[Dict[str, Any]]:
    ids = POLICE_ID_RE.findall(message)
    if not ids:
        return []
    try:
        rows = db.execute(
            text(
                """
                select call_id, cad_event_number, initial_call_type, final_call_type, priority,
                       ts, beat, latitude, longitude, content,
                       1.0 as similarity
                from police_call_embeddings
                where cad_event_number = any(:ids)
                order by ts desc
                limit :limit
                """
            ),
            {"ids": ids, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def fetch_fire_incidents(
    db: Session, embedding: List[float], limit: int
) -> List[Dict[str, Any]]:
    try:
        rows = db.execute(
            text(
                """
                select incident_id, incident_number, call_type, call_description, priority,
                       ts, address, latitude, longitude, content,
                       1 - (embedding <=> CAST(:embedding AS vector)) as similarity
                from fire_incident_embeddings
                order by embedding <=> CAST(:embedding AS vector)
                limit :limit
                """
            ),
            {"embedding": vector_to_sql(embedding), "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def fetch_police_calls(
    db: Session, embedding: List[float], limit: int
) -> List[Dict[str, Any]]:
    try:
        rows = db.execute(
            text(
                """
                select call_id, cad_event_number, initial_call_type, final_call_type, priority,
                       ts, beat, latitude, longitude, content,
                       1 - (embedding <=> CAST(:embedding AS vector)) as similarity
                from police_call_embeddings
                order by embedding <=> CAST(:embedding AS vector)
                limit :limit
                """
            ),
            {"embedding": vector_to_sql(embedding), "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def fetch_cell_summaries(
    db: Session, embedding: List[float], limit: int
) -> List[Dict[str, Any]]:
    try:
        rows = db.execute(
            text(
                """
                select cell_id, window_start, window_end, fire_total, police_total, risk_level,
                       content, 1 - (embedding <=> CAST(:embedding AS vector)) as similarity
                from cell_summary_embeddings
                order by embedding <=> CAST(:embedding AS vector)
                limit :limit
                """
            ),
            {"embedding": vector_to_sql(embedding), "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def get_risk_context() -> Optional[Dict[str, Any]]:
    try:
        snapshot = risk_router.get_risk_grid()
    except Exception as exc:
        return {"error": str(exc)}

    cells = snapshot.get("cells", [])
    top = sorted(cells, key=lambda c: c.get("risk_score", 0), reverse=True)[:8]
    return {
        "timestamp": snapshot.get("timestamp"),
        "top_cells": [
            {
                "cell_id": c.get("cell_id"),
                "risk_score": c.get("risk_score"),
                "expected_incidents": c.get("expected_incidents"),
            }
            for c in top
        ],
    }


def format_section(title: str, lines: Sequence[str]) -> str:
    if not lines:
        return f"{title}:\n- none"
    body = "\n".join(f"- {line}" for line in lines)
    return f"{title}:\n{body}"


def build_context(
    db: Session,
    message: str,
    view_state: Dict[str, Any],
    top_k: int = DEFAULT_TOP_K,
) -> Tuple[str, List[Dict[str, Any]]]:
    embedding = embed_query(message)
    targets = infer_targets(message, view_state)
    sources: List[Dict[str, Any]] = []
    sections: List[str] = []

    if "fire" in targets:
        fire_records = fetch_fire_incidents(db, embedding, top_k)
        if not fire_records:
            fire_records = keyword_search_fire(db, message, top_k)
        sources.extend(
            {**r, "source": "fire_incidents"} for r in fire_records
        )
        sections.append(
            format_section(
                "Fire incidents",
                [r["content"] for r in fire_records],
            )
        )

    if "police" in targets:
        police_records = fetch_police_calls(db, embedding, top_k)
        if not police_records:
            police_records = keyword_search_police(db, message, top_k)
        sources.extend(
            {**r, "source": "police_calls"} for r in police_records
        )
        sections.append(
            format_section(
                "Police calls",
                [r["content"] for r in police_records],
            )
        )

    if "cells" in targets:
        cell_records = fetch_cell_summaries(db, embedding, top_k)
        sources.extend(
            {**r, "source": "cell_summaries"} for r in cell_records
        )
        sections.append(
            format_section(
                "Cell summaries",
                [r["content"] for r in cell_records],
            )
        )

    if should_include_risk(message, view_state):
        risk_context = get_risk_context()
        sections.append(
            "Risk snapshot:\n"
            + json.dumps(risk_context, indent=2, default=str)
        )

    view_context = normalize_view_state(view_state)
    if view_context:
        sections.append(
            "View state:\n" + json.dumps(view_context, indent=2, default=str)
        )

    return "\n\n".join(sections), sources


def build_messages(
    system_prompt: str, user_prompt: str, history: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        trimmed = history[-MAX_HISTORY:]
        for msg in trimmed:
            role = msg.get("role")
            content = msg.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def handle_chat(
    db: Session,
    message: str,
    history: List[Dict[str, str]],
    view_state: Dict[str, Any],
) -> Dict[str, Any]:
    context, sources = build_context(db, message, view_state)

    system = (
        "You are the SERO assistant for Seattle emergency operations. "
        "Answer only using the provided context. If the context does not contain "
        "the answer, say you do not have enough data and suggest what to check. "
        "Cite incident numbers or cell IDs when available."
    )
    user = f"Context:\n{context}\n\nQuestion: {message}"

    messages = build_messages(system, user, history)
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
    )
    answer = resp.choices[0].message.content
    return {"answer": answer, "sources": sources}


def stream_chat(
    db: Session,
    message: str,
    history: List[Dict[str, str]],
    view_state: Dict[str, Any],
) -> Iterable[str]:
    context, _sources = build_context(db, message, view_state)

    system = (
        "You are the SERO assistant for Seattle emergency operations. "
        "Answer only using the provided context. If the context does not contain "
        "the answer, say you do not have enough data and suggest what to check. "
        "Cite incident numbers or cell IDs when available."
    )
    user = f"Context:\n{context}\n\nQuestion: {message}"

    messages = build_messages(system, user, history)

    stream = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if not delta:
            continue
        content = delta.content or ""
        if content:
            yield f"data:{content}\n\n"

    yield "data:[DONE]\n\n"
