from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import math
import os
import pickle
from pathlib import Path
import networkx as nx

ROUTER = APIRouter(prefix="/route", tags=["route"])

GRAPH_PATH = Path(__file__).resolve().parents[2] / "seattle_drive.pkl"

# Global graph, loaded once
G = None

def load_graph():
    global G
    if G is None:
        if not GRAPH_PATH.exists():
            raise RuntimeError(f"Graph file not found: {GRAPH_PATH}")
        with open(GRAPH_PATH, "rb") as f:
            G_loaded = pickle.load(f)
        # ensure it's a NetworkX graph object
        if not isinstance(G_loaded, (nx.Graph, nx.DiGraph, nx.MultiDiGraph)):
            raise RuntimeError("Loaded object is not a NetworkX graph")
        G = G_loaded
        print(f"Loaded road graph from {GRAPH_PATH}")
    return G

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float

class RoutePoint(BaseModel):
    lat: float
    lon: float
    time: float    # seconds along path (simple cumulative)

class RouteResponse(BaseModel):
    points: list[RoutePoint]
    total_time: float  # seconds
    total_length: float  # meters

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Straight-line distance in meters (for A* heuristic)."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

@ROUTER.on_event("startup")
def init_graph():
    # Load graph once when app starts
    load_graph()
    print("Seattle road graph loaded")

@ROUTER.post("", response_model=RouteResponse)
def route(req: RouteRequest):
    G = load_graph()

    # 1. snap to nearest graph nodes
    # nodes have 'x' (lon), 'y' (lat)
    # we do a simple nearest-node search by brute force; for better perf
    # you can build a KDTree offline and store node <-> index separately
    def nearest_node(lat, lon):
        best_node = None
        best_dist = float("inf")
        for n, data in G.nodes(data=True):
            d = haversine_m(lat, lon, data["y"], data["x"])
            if d < best_dist:
                best_dist = d
                best_node = n
        return best_node

    orig = nearest_node(req.start_lat, req.start_lon)
    dest = nearest_node(req.end_lat, req.end_lon)

    if orig is None or dest is None:
        raise HTTPException(status_code=400, detail="Could not snap points to road network")

    # 2. A* search using travel_time if present, else length
    weight_attr = "travel_time" if "travel_time" in next(iter(G.edges(data=True)))[2] else "length"

    def heuristic(u, v):
        # heuristic: straight-line distance / avg_speed
        lat1, lon1 = G.nodes[u]["y"], G.nodes[u]["x"]
        lat2, lon2 = G.nodes[v]["y"], G.nodes[v]["x"]
        d = haversine_m(lat1, lon1, lat2, lon2)
        avg_speed_mps = 12.0  # ~43 km/h
        return d / avg_speed_mps

    try:
        path_nodes = nx.astar_path(G, orig, dest, heuristic=heuristic, weight=weight_attr)
    except nx.NetworkXNoPath:
        raise HTTPException(status_code=400, detail="No route found")

    # 3. Build polyline using edge geometries, with cumulative time
    points: list[RoutePoint] = []
    total_time = 0.0
    total_length = 0.0

    def segment_distance_m(lat1, lon1, lat2, lon2) -> float:
        # use the same haversine as heuristic
        return haversine_m(lat1, lon1, lat2, lon2)

    # path_nodes: [n0, n1, n2, ...]
    for i in range(len(path_nodes) - 1):
        u = path_nodes[i]
        v = path_nodes[i + 1]

        node_u = G.nodes[u]
        node_v = G.nodes[v]

        # pick the "best" edge between u and v
        edge_data = min(
            G[u][v].values(),
            key=lambda e: e.get(weight_attr, 0.0),
        )

        seg_length = edge_data.get("length", 0.0)  # meters
        seg_time = edge_data.get("travel_time", seg_length / 12.0)  # seconds, fallback

        # Get geometry for this edge: a LineString with intermediate points
        coords = None
        geom = edge_data.get("geometry", None)
        if geom is not None:
            # shapely LineString: (x, y) = (lon, lat)
            coords = list(geom.coords)
        else:
            # fall back to straight line between nodes
            coords = [
                (node_u["x"], node_u["y"]),
                (node_v["x"], node_v["y"]),
            ]

        # We’ll distribute seg_time along this geometry by distance
        # so each vertex gets an appropriate timestamp.
        # First, compute total length along the geometry (in meters).
        dists = [0.0]
        seg_total_geom_len = 0.0
        for j in range(1, len(coords)):
            lon1, lat1 = coords[j - 1]
            lon2, lat2 = coords[j]
            d = segment_distance_m(lat1, lon1, lat2, lon2)
            seg_total_geom_len += d
            dists.append(seg_total_geom_len)

        # Avoid divide-by-zero; if geometry has no actual length, treat as a point
        if seg_total_geom_len == 0.0:
            seg_total_geom_len = 1.0

        # Now emit points along this edge geometry
        for j, (lon, lat) in enumerate(coords):
            # Skip the first point if it's identical to the last point we added
            if points:
                last = points[-1]
                if abs(last.lat - lat) < 1e-9 and abs(last.lon - lon) < 1e-9 and j == 0:
                    continue

            # fraction along this edge (0..1)
            frac = dists[j] / seg_total_geom_len
            t_here = total_time + frac * seg_time

            points.append(RoutePoint(lat=lat, lon=lon, time=t_here))

        total_time += seg_time
        total_length += seg_length

    return RouteResponse(points=points, total_time=total_time, total_length=total_length)
