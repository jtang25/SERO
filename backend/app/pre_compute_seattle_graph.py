# app/pre_compute_seattle_graph.py
import osmnx as ox
import pickle
from pathlib import Path

print("Downloading Seattle road network (drive)…")
G = ox.graph_from_place("Seattle, Washington, USA", network_type="drive")

# Add estimated speeds and travel times
G = ox.add_edge_speeds(G)        # adds 'speed_kph'
G = ox.add_edge_travel_times(G)  # adds 'travel_time' (seconds)

# Save the graph to disk with plain pickle
project_root = Path(__file__).resolve().parents[1]  # .../backend
output_path = project_root / "seattle_drive.pkl"

with open(output_path, "wb") as f:
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

print(f"Saved graph to {output_path}")
