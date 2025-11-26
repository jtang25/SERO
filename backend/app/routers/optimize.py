from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .risk import get_risk_grid as get_risk_grid_internal
from ..services.optimizer import optimize_staging

router = APIRouter()


class StationIn(BaseModel):
    station_id: str
    lat: float
    lon: float
    vehicles_current: int


class DeploymentRequest(BaseModel):
    fleet_type: str = "fire"
    stations: List[StationIn]


@router.post("/deployment")
def deployment(req: DeploymentRequest, db: Session = Depends(get_db)):
    """
    Part 1: compute target vehicles per station from the risk grid.
    Part 2: compute a minimum-cost rebalancing plan between stations.
    """
    # 1) Get the current risk snapshot from your existing risk service.
    #    DO NOT modify risk. We just call it.
    risk_snapshot = get_risk_grid_internal()
    cells = risk_snapshot["cells"]  # list of dicts, as in your /risk/latest internals

    # 2) Convert Pydantic models to plain dicts for the optimizer.
    stations = [s.dict() for s in req.stations]

    # 3) Run the two-stage optimizer (station allocation + rebalancing).
    result = optimize_staging(cells=cells, stations=stations)

    # 4) Wrap with fleet_type + timestamp and return.
    return {
        "fleet_type": req.fleet_type,
        "timestamp": risk_snapshot["timestamp"],
        "stations": result["stations"],
        "moves": result["moves"],
        "total_travel_cost": result["total_travel_cost"],
    }
