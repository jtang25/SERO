from typing import List, Dict, Tuple
import math

from ortools.linear_solver import pywraplp


def euclidean_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Simple Euclidean distance in (lat, lon) degrees.
    Good enough for local rebalancing within Seattle.
    """
    dlat = lat1 - lat2
    dlon = lon1 - lon2
    return math.sqrt(dlat * dlat + dlon * dlon)


# ---------- Part 1: Station-level target distribution ----------


def compute_station_risk(
    cells: List[Dict],
    stations: List[Dict],
    risk_key: str = "expected_incidents",
    fallback_risk_key: str = "risk_score",
) -> Dict[str, float]:
    """
    Given the risk grid (cells) and stations, assign each cell to its nearest station
    and sum the risk over cells to get per-station local_risk.

    cells: output from your risk grid internal function (risk_snapshot["cells"])
           Each cell dict should have: "lat", "lon", and either risk_key or fallback_risk_key.
    stations: list of dicts with keys: station_id, lat, lon, vehicles_current

    Returns: dict station_id -> local_risk (float)
    """
    station_risk = {s["station_id"]: 0.0 for s in stations}

    if not cells or not stations:
        return station_risk

    for cell in cells:
        # Prefer expected_incidents if present, otherwise fall back to risk_score.
        risk_val = cell.get(risk_key, None)
        if risk_val is None:
            # Some internal variants may use "risk" instead of "risk_score"
            risk_val = cell.get(fallback_risk_key, cell.get("risk", 0.0))

        # Skip cells with essentially zero risk to save a bit of work.
        if risk_val is None or risk_val <= 0.0:
            continue

        lat_i = cell["lat"]
        lon_i = cell["lon"]

        # Find nearest station by Euclidean distance in lat/lon.
        best_station_id = None
        best_dist = None

        for s in stations:
            d = euclidean_distance(lat_i, lon_i, s["lat"], s["lon"])
            if best_dist is None or d < best_dist:
                best_dist = d
                best_station_id = s["station_id"]

        if best_station_id is not None:
            station_risk[best_station_id] += float(risk_val)

    return station_risk


def compute_target_distribution(
    stations: List[Dict],
    station_risk: Dict[str, float],
) -> List[Dict]:
    """
    Compute vehicles_target per station using a proportional rule:

        vehicles_target_s ≈ V_total * local_risk_s / sum(local_risk)

    and then round to integers while preserving the total fleet size.

    If total local risk is zero (no risk anywhere), we simply keep
    vehicles_target = vehicles_current for all stations.

    Returns a new list of station dicts with "vehicles_target" and "local_risk" added.
    """
    # Total fleet size (conserved).
    V_total = sum(max(int(s.get("vehicles_current", 0)), 0) for s in stations)

    # Attach local_risk to each station.
    stations_out = []
    total_risk = 0.0
    for s in stations:
        r = float(station_risk.get(s["station_id"], 0.0))
        s_copy = dict(s)
        s_copy["local_risk"] = r
        stations_out.append(s_copy)
        total_risk += r

    # Edge case: no risk anywhere -> keep current distribution.
    if total_risk <= 0.0 or V_total <= 0:
        for s in stations_out:
            s["vehicles_target"] = int(s.get("vehicles_current", 0))
        return stations_out

    # Compute raw fractional targets.
    raw_targets: List[Tuple[int, float, float]] = []  # (index, raw_target, frac_part)
    for idx, s in enumerate(stations_out):
        local_risk = s["local_risk"]
        if local_risk <= 0.0:
            rt = 0.0
        else:
            rt = V_total * (local_risk / total_risk)
        frac = rt - math.floor(rt)
        raw_targets.append((idx, rt, frac))

    # First pass: floor everything.
    targets_int = [0 for _ in stations_out]
    allocated = 0
    for idx, rt, _ in raw_targets:
        t = int(math.floor(rt))
        targets_int[idx] = t
        allocated += t

    # We may have some remaining units to distribute due to rounding.
    remaining = V_total - allocated
    if remaining > 0:
        # Sort by fractional part descending and give +1 to top "remaining" stations.
        raw_targets_sorted = sorted(raw_targets, key=lambda x: x[2], reverse=True)
        for i in range(min(remaining, len(raw_targets_sorted))):
            idx = raw_targets_sorted[i][0]
            targets_int[idx] += 1

    # Attach final integer targets.
    for idx, s in enumerate(stations_out):
        s["vehicles_target"] = int(targets_int[idx])

    return stations_out


# ---------- Part 2: Rebalancing plan as min-cost flow ----------


def compute_rebalancing_moves(stations: List[Dict]) -> Tuple[List[Dict], float]:
    """
    Given stations with vehicles_current and vehicles_target,
    compute a minimum-cost set of moves between stations such that:

        - Final vehicles at each station match vehicles_target
        - Total travel cost is minimized
        - Travel cost from s to t is Euclidean distance between station coords

    This is formulated as an integer min-cost flow using OR-Tools CBC solver.

    Returns:
        moves: list of dicts with from_station_id, to_station_id, num_vehicles, distance
        total_cost: sum(num_vehicles * distance) over all moves
    """
    n = len(stations)
    if n == 0:
        return [], 0.0

    # Compute net supply/demand at each station: delta_s = current - target
    deltas: List[int] = []
    for s in stations:
        cur = int(s.get("vehicles_current", 0))
        tgt = int(s.get("vehicles_target", 0))
        deltas.append(cur - tgt)

    # Sanity check: sum of deltas should be 0 (conserved fleet size).
    total_delta = sum(deltas)
    if total_delta != 0:
        # This should not happen if targets are computed correctly,
        # but we guard against it. In case of mismatch, do no moves.
        return [], 0.0

    # If everyone is already at target, there is nothing to do.
    if all(d == 0 for d in deltas):
        return [], 0.0

    solver = pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        raise RuntimeError("No solver available for rebalancing")

    # Decision variables: flow[s, t] = number of vehicles moved from s to t (integer >= 0).
    # We don't need flows s->s, so skip those.
    flow: Dict[Tuple[int, int], "pywraplp.Variable"] = {}
    for s_idx in range(n):
        for t_idx in range(n):
            if s_idx == t_idx:
                continue
            flow[(s_idx, t_idx)] = solver.IntVar(0.0, solver.infinity(), f"f_{s_idx}_{t_idx}")

    # Flow conservation at each station:
    #
    #   sum_t flow[s, t] - sum_u flow[u, s] = delta_s
    #
    # If delta_s > 0 -> net outflow (station has surplus),
    # If delta_s < 0 -> net inflow (station needs vehicles).
    for s_idx in range(n):
        out_expr = solver.Sum(flow[(s_idx, t)] for t in range(n) if s_idx != t)
        in_expr = solver.Sum(flow[(u, s_idx)] for u in range(n) if u != s_idx)
        solver.Add(out_expr - in_expr == deltas[s_idx])

    # Objective: minimize total travel cost sum_{s,t} flow[s,t] * d_station[s,t].
    objective = solver.Objective()
    for (s_idx, t_idx), var in flow.items():
        s = stations[s_idx]
        t = stations[t_idx]
        cost = euclidean_distance(s["lat"], s["lon"], t["lat"], t["lon"])
        objective.SetCoefficient(var, cost)
    objective.SetMinimization()

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("No optimal rebalancing plan found")

    # Extract non-zero flows as moves.
    moves: List[Dict] = []
    total_cost = 0.0
    for (s_idx, t_idx), var in flow.items():
        amount = int(round(var.solution_value()))
        if amount <= 0:
            continue
        from_s = stations[s_idx]
        to_s = stations[t_idx]
        dist = euclidean_distance(from_s["lat"], from_s["lon"], to_s["lat"], to_s["lon"])
        cost = amount * dist
        total_cost += cost
        moves.append(
            {
                "from_station_id": from_s["station_id"],
                "to_station_id": to_s["station_id"],
                "num_vehicles": amount,
                "distance": dist,
            }
        )

    return moves, total_cost


# ---------- Top-level function used by the router ----------


def optimize_staging(
    cells: List[Dict],
    stations: List[Dict],
) -> Dict[str, object]:
    """
    Top-level interface used by the FastAPI router.

    Inputs:
        cells: risk grid cells (from get_risk_grid_internal(db))
        stations: list of stations, each with station_id, lat, lon, vehicles_current

    Steps:
        Part 1: compute local_risk per station and an integer vehicles_target distribution.
        Part 2: compute a min-cost rebalancing plan from current to target.

    Returns:
        {
          "stations": [ {station_id, lat, lon, vehicles_current, vehicles_target, local_risk}, ... ],
          "moves": [ {from_station_id, to_station_id, num_vehicles, distance}, ... ],
          "total_travel_cost": float
        }
    """
    # Part 1: station-level risk + target vehicles.
    station_risk = compute_station_risk(cells=cells, stations=stations)
    stations_with_targets = compute_target_distribution(stations=stations, station_risk=station_risk)

    # Part 2: rebalancing plan to move from current -> target.
    moves, total_cost = compute_rebalancing_moves(stations_with_targets)

    return {
        "stations": stations_with_targets,
        "moves": moves,
        "total_travel_cost": total_cost,
    }
