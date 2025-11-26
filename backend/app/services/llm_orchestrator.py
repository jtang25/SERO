# app/llm/llm_orchestrator.py
import re
import json
from datetime import datetime

from sqlalchemy.orm import Session
from openai import OpenAI

from ..config import OPENAI_API_KEY
from .feature_builder import FeatureBuilder
from .risk_model import RiskModel
from .optimizer import optimize_staging
from .grid_indexer import GridIndexer

client = OpenAI(api_key=OPENAI_API_KEY)

# Seattle-ish grid
grid = GridIndexer(47.48, 47.75, -122.45, -122.22, 0.01, 0.01)
feature_builder = FeatureBuilder(grid)

# Single RiskModel that internally uses BOTH classifier + regressor
risk_model = RiskModel("app/models/risk_model.pkl")


def classify_intent(message: str) -> str:
    m = message.lower()
    if any(k in m for k in ["deploy", "place", "staging", "where should we put", "optimize"]):
        return "optimize_deployment"
    if any(k in m for k in ["risk", "hotspot", "high risk"]):
        return "explain_risk"
    return "generic_ops_question"


def extract_num_units(message: str, default: int = 6) -> int:
    nums = re.findall(r"\d+", message)
    return int(nums[0]) if nums else default


def _llm(system_prompt: str, user_prompt: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


def handle_message(db: Session, message: str, view_state: dict):
    intent = classify_intent(message)
    horizon_hours = view_state.get("horizon_hours", 3)
    ts_now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    # ------------------------------------------------------------------
    # 1) Build snapshot features at ts_now
    # ------------------------------------------------------------------
    df = feature_builder.build_snapshot_features(db, ts_now)

    # Probability of any incident (classification)
    probs = risk_model.predict_proba(df)

    # Expected number of incidents (regression)
    expected = risk_model.predict_expected(df)

    # ------------------------------------------------------------------
    # 2) Pack per-cell risk info (probability + expected volume)
    # ------------------------------------------------------------------
    cells = []
    for cell_id, p, exp in zip(df["cell_id"].values, probs, expected):
        lat, lon = grid.cell_to_centroid(cell_id)
        cells.append(
            {
                "cell_id": int(cell_id),
                "lat": lat,
                "lon": lon,
                "risk": float(p),                   # P(incident > 0)
                "expected_incidents": float(exp),   # E[future_total]
            }
        )

    risk_snapshot = {
        "timestamp": ts_now.isoformat(),
        "horizon_hours": horizon_hours,
        "cells": cells,
    }

    # ------------------------------------------------------------------
    # 3) Intent-specific behavior
    # ------------------------------------------------------------------
    if intent == "optimize_deployment":
        # How many units to deploy?
        num_units = extract_num_units(message, view_state.get("num_units", 6))

        # Candidates: we just need ids + coords; optimizer can use risk/exp from 'cells'
        candidates = [
            {"cell_id": c["cell_id"], "lat": c["lat"], "lon": c["lon"]}
            for c in cells
        ]

        # Optimizer gets full risk info in `cells`
        units = optimize_staging(cells, candidates, num_units)

        context = json.dumps(
            {
                "num_units": num_units,
                "risk_snapshot": risk_snapshot,
                "deployment_plan": units,
            },
            default=float,
        )

        system = (
            "You are an emergency operations planner for Seattle. "
            "Explain the given deployment plan based only on the JSON. "
            "Use both the risk probability and expected incident volume to justify decisions."
        )
        user = f"Operator asked: {message}\n\nHere is the plan JSON:\n{context}"
        answer = _llm(system, user)

        return {
            "intent": intent,
            "answer": answer,
            "risk_snapshot": risk_snapshot,
            "deployment_plan": units,
        }

    elif intent == "explain_risk":
        # Top hotspots by risk; expected_incidents is available in JSON too
        top = sorted(cells, key=lambda c: c["risk"], reverse=True)[:10]
        context = json.dumps({"top_hotspots": top}, default=float)

        system = (
            "You are an emergency operations planner. Describe high-risk areas in Seattle "
            "based only on the provided JSON. Consider BOTH the probability of incidents "
            "and the expected number of incidents when explaining hotspots."
        )
        user = f"Operator asked: {message}\n\nHere are the top hotspots:\n{context}"
        answer = _llm(system, user)

        return {
            "intent": intent,
            "answer": answer,
            "risk_snapshot": risk_snapshot,
        }

    else:
        # generic: summarize situation with both risk & expected volume
        top = sorted(cells, key=lambda c: c["risk"], reverse=True)[:5]
        context = json.dumps({"top_hotspots": top}, default=float)

        system = (
            "You are an emergency operations planner. Use the JSON to summarize the current situation, "
            "commenting on both where incidents are most likely and where the expected volume is highest."
        )
        user = f"Operator asked: {message}\n\nHere's the risk summary:\n{context}"
        answer = _llm(system, user)

        return {
            "intent": intent,
            "answer": answer,
            "risk_snapshot": risk_snapshot,
        }
