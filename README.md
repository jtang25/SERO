# Seattle Emergency Risk Optimizer (SERO)

SERO is a map-based emergency fleet planning app inspired by Palantir-style AIP workflows.

It ingests Seattle fire/police 911 open data into a Supabase (Postgres) backend, learns a
spatio-temporal risk model over the city, and computes optimized vehicle deployments across
stations. Planners can visualize risk in real-time, edit station layouts, and run an optimizer
that recommends concrete rebalancing moves to better cover predicted demand.


https://github.com/user-attachments/assets/9714dae9-debc-4175-b34e-f253036de3bd

## Features

- **Live risk heatmap**
  - City grid over Seattle with per-cell risk scores in “the next few hours”.
  - Shows both probability of at least one incident and expected incident volume.

- **Station editor**
  - Configure fire/police/EMS stations with current vehicle counts.
  - Visualize deployments and station catchments on an interactive map.

- **Optimization engine**
  - Two-stage decision layer:
    1. Aggregates predicted demand into local risk around each station.
    2. Solves a min-cost flow to compute vehicle moves between stations while preserving fleet size.
  - Returns explicit moves: “Send 2 vehicles from FS3 → FS1”.

- **AIP-style web UI**
  - React + TypeScript + Mapbox dashboard.
  - Risk grid, stations, and rebalancing moves rendered together for human-in-the-loop planning.

---

## Tech Stack

**Data & Storage**

- Supabase (managed Postgres) for:
  - `fire_incidents` – raw fire calls
  - `police_calls` – raw police calls
  - `incident_counts` – per-grid-cell, per-hour counts used by the risk model

**Backend**

- Python 3
- FastAPI (REST APIs)
- SQLAlchemy for DB access
- XGBoost for classification / regression
- scikit-learn for preprocessing (SimpleImputer, etc.)
- OR-Tools (CBC solver) for min-cost flow optimization
- Uvicorn for local dev server

**Frontend**

- Next.js / React / TypeScript
- Mapbox GL JS via `react-map-gl`
- Tailwind CSS

---

## High-Level Architecture

```text
Raw 911 Data ──► Supabase/Postgres ──► Offline Training (notebooks/)
                                       │
                                       ▼
                             risk_xgb.pkl (classifier)
                             risk_xgb_total.pkl (regressor)
                             risk_imputer.pkl
                                       │
                       ┌───────────────┴────────────────┐
                       ▼                                ▼
                 /risk/latest                     /optimize/deployment
              (FastAPI router)                   (FastAPI router)
                       │                                │
                       ▼                                ▼
              React/TS + Mapbox UI  ◄─────────────── User
