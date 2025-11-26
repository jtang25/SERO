# app/pre_compute_seattle_graph.py
import osmnx as ox
import pickle
from pathlib import Path

print("Downloading Seattle road network (drive)…")
G = ox.graph_from_place("Seattle, Washington, USA", network_type="drive")

# OPTIONAL: if you wanted only the largest connected component, you would do:
# import networkx as nx
# G = nx.utils.misc.largest_connected_component(G)  # or similar
# but you said you want everything, so we skip that.

# Add estimated speeds and travel times (optional but nice for routing)
G = ox.add_edge_speeds(G)        # adds 'speed_kph'
G = ox.add_edge_travel_times(G)  # adds 'travel_time' (seconds)

# Save the graph to disk with plain pickle
project_root = Path(__file__).resolve().parents[1]  # .../backend
output_path = project_root / "seattle_drive.pkl"

with open(output_path, "wb") as f:
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

print(f"Saved graph to {output_path}")
