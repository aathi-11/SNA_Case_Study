"""
Plotting module for Football Passing Networks.
Visualizes passing networks on mplsoccer pitches and plots fragility curves.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import networkx as nx
from src.graphs import build_team_graph
from src.communities import detect_louvain_communities
from src.metrics import compute_node_removal_vulnerability

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PLOTS_DIR = DATA_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

def plot_passing_network(match_id: int, team_name: str, save_path: Path = None):
    """
    Draw mplsoccer pitch overlay showing Louvain communities, edge thicknesses, and betweenness sizes.
    """
    G = build_team_graph(match_id, team_name)
    comm_res = detect_louvain_communities(G, num_seeds=5)
    partition = comm_res["best_partition"]
    
    # Calculate Betweenness for node size
    try:
        bet = nx.betweenness_centrality(G, weight="distance", normalized=True)
    except Exception:
        bet = {n: 0.1 for n in G.nodes()}
        
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#22312b', line_color='#c7d5cc')
    fig, ax = pitch.draw(figsize=(12, 8))
    
    # Colors for communities
    colors = ['#ff7f0e', '#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
    
    # Draw edges
    for u, v, data in G.edges(data=True):
        x1, y1 = G.nodes[u]['avg_x'], G.nodes[u]['avg_y']
        x2, y2 = G.nodes[v]['avg_x'], G.nodes[v]['avg_y']
        w = data['weight']
        
        # Only draw edges with weight > 1 for clarity
        if w > 1:
            pitch.lines(x1, y1, x2, y2, ax=ax, color='#c7d5cc', 
                        lw=w * 0.3, alpha=0.5, zorder=1)
            
    # Draw nodes
    for node, data in G.nodes(data=True):
        x, y = data['avg_x'], data['avg_y']
        c_id = partition.get(node, 0)
        c_color = colors[c_id % len(colors)]
        
        # Node size proportional to betweenness
        s = 50 + bet.get(node, 0) * 2000
        
        pitch.scatter(x, y, ax=ax, c=c_color, s=s, edgecolors='black', linewidth=1.5, zorder=2)
        ax.annotate(node.split()[-1], (x, y-2), color='white', ha='center', va='center', fontsize=10, zorder=3)
        
    ax.set_title(f"Passing Network: {team_name}", color="black", fontsize=16)
    
    if save_path:
        plt.savefig(save_path, bbox_inches="tight")
        plt.close()
    else:
        plt.show()

def plot_fragility_curve(match_id: int, team_name: str, save_path: Path = None):
    """
    Horizontal bar chart of global efficiency drop per player (ΔE_k).
    """
    G = build_team_graph(match_id, team_name)
    vuln_dict = compute_node_removal_vulnerability(G)
    
    if not vuln_dict:
        return
        
    df = pd.DataFrame.from_dict(vuln_dict, orient='index').reset_index()
    df.columns = ["player", "efficiency_drop_pct", "subgraph_efficiency"]
    df = df.sort_values(by="efficiency_drop_pct", ascending=True)
    
    plt.figure(figsize=(10, 8))
    bars = plt.barh(df["player"], df["efficiency_drop_pct"], color='skyblue')
    
    # Highlight the SPOF player if drop > 25%
    for i, bar in enumerate(bars):
        if df.iloc[i]["efficiency_drop_pct"] > 25.0:
            bar.set_color('salmon')
            
    plt.xlabel("Global Efficiency Drop (%)")
    plt.title(f"Node-Removal Fragility: {team_name}")
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    
    if save_path:
        plt.savefig(save_path, bbox_inches="tight")
        plt.close()
    else:
        plt.show()
