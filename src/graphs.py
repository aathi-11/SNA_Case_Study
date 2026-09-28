"""
Graph construction and Gephi export utilities for Football Passing Networks.
Builds NetworkX DiGraph objects with spatial nodes and distance-weighted edges.
Supports export to GraphML and Gephi CSV formats.
"""

import os
from pathlib import Path
import pandas as pd
import networkx as nx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GEPHI_DIR = DATA_DIR / "gephi"


def build_team_graph(match_id: int, team_name: str) -> nx.DiGraph:
    """
    Build a NetworkX DiGraph for a specific team in a match.
    
    Nodes: Players, with spatial attributes (avg_x, avg_y, passes_made, passes_received).
    Edges: Directed passer -> recipient, weighted by pass count.
           Edge distance = 1.0 / weight for path calculations.
    """
    edges_df = pd.read_parquet(PROCESSED_DIR / "passing_edges.parquet")
    players_df = pd.read_parquet(PROCESSED_DIR / "player_match_stats.parquet")
    
    # Filter for team match
    match_edges = edges_df[(edges_df["match_id"] == match_id) & (edges_df["team_name"] == team_name)]
    match_players = players_df[(players_df["match_id"] == match_id) & (players_df["team_name"] == team_name)]
    
    G = nx.DiGraph(match_id=match_id, team_name=team_name)
    
    # Add nodes with spatial & pass statistics
    for _, prow in match_players.iterrows():
        G.add_node(
            prow["player_name"],
            player_id=int(prow["player_id"]),
            team=team_name,
            tactical_line=prow.get("tactical_line", "Unknown"),
            nominal_position=prow.get("nominal_position", "Unknown"),
            avg_x=float(prow["avg_x"]),
            avg_y=float(prow["avg_y"]),
            passes_made=int(prow["passes_made"]),
            passes_received=int(prow["passes_received"]),
        )
        
    # Add directed edges
    for _, erow in match_edges.iterrows():
        w = int(erow["weight"])
        if w > 0:
            G.add_edge(
                erow["passer_name"],
                erow["recipient_name"],
                weight=w,
                distance=1.0 / float(w),
                avg_distance=float(erow["avg_distance"]),
                progressive_passes=int(erow["progressive_passes"]),
            )
            
    return G


def export_graphml(G: nx.DiGraph, filepath: Path) -> Path:
    """Export a NetworkX graph to GraphML format for Gephi."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, filepath)
    return filepath


def export_gephi_csv(G: nx.DiGraph, output_prefix: str) -> tuple:
    """
    Export node and edge tables to CSV format specifically formatted for Gephi Data Laboratory import.
    
    Nodes CSV columns: Id, Label, Team, avg_x, avg_y, passes_made, passes_received
    Edges CSV columns: Source, Target, Type, Weight, Distance
    """
    GEPHI_DIR.mkdir(parents=True, exist_ok=True)
    
    nodes_data = []
    for node, data in G.nodes(data=True):
        nodes_data.append({
            "Id": node,
            "Label": node,
            "Team": data.get("team", ""),
            "tactical_line": data.get("tactical_line", ""),
            "nominal_position": data.get("nominal_position", ""),
            "avg_x": data.get("avg_x", 0.0),
            "avg_y": data.get("avg_y", 0.0),
            "passes_made": data.get("passes_made", 0),
            "passes_received": data.get("passes_received", 0),
        })
    nodes_df = pd.DataFrame(nodes_data)
    nodes_csv = GEPHI_DIR / f"{output_prefix}_nodes.csv"
    nodes_df.to_csv(nodes_csv, index=False)
    
    edges_data = []
    for u, v, data in G.edges(data=True):
        edges_data.append({
            "Source": u,
            "Target": v,
            "Type": "Directed",
            "Weight": data.get("weight", 1),
            "Distance": data.get("distance", 1.0),
            "Avg_Pass_Distance": data.get("avg_distance", 0.0),
            "Progressive_Passes": data.get("progressive_passes", 0),
        })
    edges_df = pd.DataFrame(edges_data)
    edges_csv = GEPHI_DIR / f"{output_prefix}_edges.csv"
    edges_df.to_csv(edges_csv, index=False)
    
    return nodes_csv, edges_csv


def export_all_sample_gephi_graphs():
    """Export featured sample matches to data/gephi/ directory."""
    GEPHI_DIR.mkdir(parents=True, exist_ok=True)
    team_summary = pd.read_parquet(PROCESSED_DIR / "team_match_summary.parquet")
    
    print("Exporting sample match passing networks to Gephi GraphML & CSV formats...")
    # Export top 4 iconic matches (e.g. World Cup finals/semis)
    sample_matches = team_summary.head(8)  # 4 matches * 2 teams = 8 team graphs
    
    for _, row in sample_matches.iterrows():
        match_id = row["match_id"]
        team_name = row["team_name"]
        safe_team = team_name.replace(" ", "_").lower()
        
        G = build_team_graph(match_id, team_name)
        
        # GraphML
        gml_path = GEPHI_DIR / f"match_{match_id}_{safe_team}.graphml"
        export_graphml(G, gml_path)
        
        # Gephi CSVs
        export_gephi_csv(G, f"match_{match_id}_{safe_team}")
        
    print(f"Exported sample Gephi files to {GEPHI_DIR}")


if __name__ == "__main__":
    export_all_sample_gephi_graphs()
