import json
import osmnx as ox

# ---------- 1. Build a road graph for Seattle (drivable roads only) ----------
print("Downloading Seattle road network...")
G = ox.graph_from_place("Seattle, Washington, USA", network_type="drive")

# ---------- 2. Helper to make one routed Trip ----------
def make_trip(
    trip_id: str,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    vehicle_type: str = "fire_truck",
    side: str = "friendly",
    seconds_per_step: float = 5.0,
):
    """
    Build a single trip that follows roads.

    We:
    - snap start/end to nearest road nodes
    - compute shortest path by distance
    - turn each node into a point with an increasing time
    """

    # snap to nearest nodes on the road graph
    orig = ox.distance.nearest_nodes(G, start_lon, start_lat)
    dest = ox.distance.nearest_nodes(G, end_lon, end_lat)

    # shortest path by edge length (meters)
    route = ox.shortest_path(G, orig, dest, weight="length")

    if route is None:
        raise RuntimeError(f"Could not find route for {trip_id}")

    # coordinates per node (x = lon, y = lat)
    coords = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in route]

    path = []
    t = 0.0
    for lon, lat in coords:
        path.append({"time": t, "lon": lon, "lat": lat})
        t += seconds_per_step

    return {
        "id": trip_id,
        "type": vehicle_type,
        "side": side,
        "path": path,
    }


# ---------- 3. Define a few example routes ----------
trips = [
    # Pike Place Market -> Chinatown / Intl District
    make_trip(
        "veh_101",
        start_lat=47.6095,
        start_lon=-122.3425,
        end_lat=47.5981,
        end_lon=-122.3270,
        vehicle_type="fire_truck",
    ),
    # Belltown -> First Hill
    make_trip(
        "veh_202",
        start_lat=47.6153,
        start_lon=-122.3470,
        end_lat=47.6080,
        end_lon=-122.3220,
        vehicle_type="ambulance",
    ),
]

# ---------- 4. Dump to JSON for the frontend ----------
output_path = "trips_road_demo.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(trips, f, indent=2)

print(f"Wrote {output_path} with {len(trips)} trips")
