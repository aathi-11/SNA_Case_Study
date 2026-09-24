"""
Network metrics computation module for Football Passing Networks.
Calculates team-level and player-level network metrics across all team-match passing graphs.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
from src.graphs import build_team_graph

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"


def freeman_degree_centralization(G: nx.DiGraph) -> float:
    """
    Compute Freeman Degree Centralization for a directed graph:
    C_D = sum(max_deg - deg_i) / ((N - 1) * (N - 2))
    Uses total degree (in-degree + out-degree).
    """
    N = G.number_of_nodes()
    if N <= 2:
        return 0.0
    degrees = [d for _, d in G.degree()]
    max_deg = max(degrees)
    max_possible = (N - 1) * (N - 2)
    return float(sum(max_deg - d for d in degrees) / max_possible)


def freeman_betweenness_centralization(bet_dict: dict, N: int) -> float:
    """
    Compute Freeman Betweenness Centralization:
    C_B = sum(max_bet - bet_i) / (N - 1)
    """
    if N <= 2:
        return 0.0
    bets = list(bet_dict.values())
    max_bet = max(bets)
    return float(sum(max_bet - b for b in bets) / (N - 1))


def compute_team_metrics(G: nx.DiGraph) -> dict:
    """Compute all structural team-level passing network metrics."""
    N = G.number_of_nodes()
    if N < 2:
        return {}
        
    # Density
    density = nx.density(G)
    
    # Reciprocity
    reciprocity = nx.reciprocity(G)
    
    # Weighted Betweenness (using distance = 1/weight)
    try:
        bet = nx.betweenness_centrality(G, weight="distance", normalized=True)
    except Exception:
        bet = {n: 0.0 for n in G.nodes()}
        
    bet_centralization = freeman_betweenness_centralization(bet, N)
    degree_centralization = freeman_degree_centralization(G)
    
    # Playmaker Share (top betweenness player share)
    sum_bet = sum(bet.values())
    top_playmaker = max(bet, key=bet.get) if bet else "None"
    top_bet = bet[top_playmaker] if bet else 0.0
    playmaker_share = (top_bet / sum_bet) if sum_bet > 0 else 0.0
    
    # Weighted Clustering Coefficient (on undirected projection)
    G_undirected = G.to_undirected(reciprocal=False)
    try:
        clustering_dict = nx.clustering(G_undirected, weight="weight")
        avg_clustering = float(np.mean(list(clustering_dict.values())))
    except Exception:
        avg_clustering = 0.0
        
    # Global Efficiency (average inverse shortest distance)
    try:
        global_eff = float(nx.global_efficiency(G_undirected))
    except Exception:
        global_eff = 0.0
        
    return {
        "num_players": N,
        "num_edges": G.number_of_edges(),
        "density": float(density),
        "reciprocity": float(reciprocity),
        "degree_centralization": float(degree_centralization),
        "betweenness_centralization": float(bet_centralization),
        "weighted_clustering": float(avg_clustering),
        "global_efficiency": float(global_eff),
        "playmaker_name": top_playmaker,
        "playmaker_betweenness": float(top_bet),
        "playmaker_share": float(playmaker_share),
    }


def compute_player_metrics(G: nx.DiGraph) -> list:
    """Compute player-level centrality metrics (Degree, Betweenness, Eigenvector, Closeness, PageRank)."""
    N = G.number_of_nodes()
    if N == 0:
        return []
        
    # Weighted Betweenness (distance = 1/weight)
    try:
        betweenness = nx.betweenness_centrality(G, weight="distance", normalized=True)
    except Exception:
        betweenness = {n: 0.0 for n in G.nodes()}
        
    # Eigenvector / PageRank
    try:
        eigenvector = nx.eigenvector_centrality_numpy(G, weight="weight")
    except Exception:
        try:
            eigenvector = nx.pagerank(G, weight="weight")
        except Exception:
            eigenvector = {n: 0.0 for n in G.nodes()}
            
    # Closeness Centrality (distance = 1/weight)
    try:
        closeness = nx.closeness_centrality(G, distance="distance")
    except Exception:
        closeness = {n: 0.0 for n in G.nodes()}
        
    in_deg_weighted = dict(G.in_degree(weight="weight"))
    out_deg_weighted = dict(G.out_degree(weight="weight"))
    in_deg_unweighted = dict(G.in_degree())
    out_deg_unweighted = dict(G.out_degree())
    
    player_metrics = []
    for node, data in G.nodes(data=True):
        player_metrics.append({
            "player_name": node,
            "player_id": data.get("player_id"),
            "avg_x": data.get("avg_x", 0.0),
            "avg_y": data.get("avg_y", 0.0),
            "in_degree_weighted": int(in_deg_weighted.get(node, 0)),
            "out_degree_weighted": int(out_deg_weighted.get(node, 0)),
            "total_degree_weighted": int(in_deg_weighted.get(node, 0) + out_deg_weighted.get(node, 0)),
            "in_degree_unweighted": int(in_deg_unweighted.get(node, 0)),
            "out_degree_unweighted": int(out_deg_unweighted.get(node, 0)),
            "betweenness_centrality": float(betweenness.get(node, 0.0)),
            "eigenvector_centrality": float(eigenvector.get(node, 0.0)),
            "closeness_centrality": float(closeness.get(node, 0.0)),
        })
        
    return player_metrics


def run_metrics_pipeline():
    """Compute team and player network metrics across all 256 team-matches and export Parquet files."""
    team_summary_df = pd.read_parquet(PROCESSED_DIR / "team_match_summary.parquet")
    
    team_metrics_list = []
    player_metrics_list = []
    
    print(f"Computing network centrality & structural metrics for {len(team_summary_df)} team-matches...")
    
    for idx, row in team_summary_df.iterrows():
        match_id = row["match_id"]
        team_name = row["team_name"]
        
        G = build_team_graph(match_id, team_name)
        
        # Team level
        tm = compute_team_metrics(G)
        tm_combined = {**row.to_dict(), **tm}
        team_metrics_list.append(tm_combined)
        
        # Player level
        pm_list = compute_player_metrics(G)
        for pm in pm_list:
            pm["match_id"] = match_id
            pm["team_name"] = team_name
            pm["competition_name"] = row["competition_name"]
            pm["season_name"] = row["season_name"]
            pm["result"] = row["result"]
            player_metrics_list.append(pm)
            
    print("Saving network metrics Parquet tables...")
    
    team_metrics_parquet = PROCESSED_DIR / "team_network_metrics.parquet"
    pd.DataFrame(team_metrics_list).to_parquet(team_metrics_parquet, index=False)
    print(f"  - Team Network Metrics: {team_metrics_parquet} ({len(team_metrics_list)} rows)")
    
    player_metrics_parquet = PROCESSED_DIR / "player_network_metrics.parquet"
    pd.DataFrame(player_metrics_list).to_parquet(player_metrics_parquet, index=False)
    print(f"  - Player Network Metrics: {player_metrics_parquet} ({len(player_metrics_list)} rows)")
    
    print("Network metrics pipeline completed successfully!")


if __name__ == "__main__":
    run_metrics_pipeline()
