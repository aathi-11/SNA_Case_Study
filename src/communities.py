"""
Community detection module for Football Passing Networks.
Executes multi-seed Louvain algorithm to detect tactical sub-units
and compares them against nominal positional lines using NMI/ARI.
"""

import numpy as np
import networkx as nx
from sklearn.metrics import normalized_mutual_info_score, adjusted_rand_score
from pathlib import Path
import pandas as pd
from src.graphs import build_team_graph

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def detect_louvain_communities(G: nx.DiGraph, num_seeds: int = 20) -> dict:
    """
    Run Louvain community detection across multiple random seeds.
    Returns the best partition (highest modularity) and the distribution of modularity scores.
    """
    G_undirected = G.to_undirected(reciprocal=False)
    
    if G_undirected.number_of_edges() == 0:
        return {
            "best_partition": {n: 0 for n in G.nodes()},
            "best_modularity": 0.0,
            "modularity_mean": 0.0,
            "modularity_std": 0.0
        }
        
    modularities = []
    best_modularity = -1.0
    best_partition = None
    
    for seed in range(num_seeds):
        # Louvain heuristic for community detection
        partition = nx.community.louvain_communities(G_undirected, weight="weight", seed=seed)
        
        # Convert list of sets to node->community_id dict
        part_dict = {}
        for comm_id, comm_nodes in enumerate(partition):
            for node in comm_nodes:
                part_dict[node] = comm_id
                
        # Calculate modularity
        try:
            mod = nx.community.modularity(G_undirected, partition, weight="weight")
        except Exception:
            mod = 0.0
            
        modularities.append(mod)
        if mod > best_modularity:
            best_modularity = mod
            best_partition = part_dict
            
    return {
        "best_partition": best_partition,
        "best_modularity": best_modularity,
        "modularity_mean": float(np.mean(modularities)),
        "modularity_std": float(np.std(modularities))
    }

def calculate_nmi_ari(G: nx.DiGraph, partition: dict) -> dict:
    """
    Compare detected communities against nominal tactical lines (DF, MF, FW, GK).
    Calculates Normalized Mutual Information (NMI) and Adjusted Rand Index (ARI).
    """
    nodes = list(G.nodes())
    if not nodes or not partition:
        return {"nmi": 0.0, "ari": 0.0}
        
    # True labels (nominal tactical lines)
    true_labels = [G.nodes[n].get("tactical_line", "Unknown") for n in nodes]
    
    # Predicted labels (detected communities)
    pred_labels = [partition.get(n, -1) for n in nodes]
    
    nmi = normalized_mutual_info_score(true_labels, pred_labels)
    ari = adjusted_rand_score(true_labels, pred_labels)
    
    return {
        "nmi": float(nmi),
        "ari": float(ari)
    }

def analyze_team_communities(match_id: int, team_name: str) -> dict:
    """
    Build the team graph and compute community metrics.
    """
    G = build_team_graph(match_id, team_name)
    comm_results = detect_louvain_communities(G)
    align_scores = calculate_nmi_ari(G, comm_results["best_partition"])
    
    return {
        "match_id": match_id,
        "team_name": team_name,
        "modularity_mean": comm_results["modularity_mean"],
        "modularity_std": comm_results["modularity_std"],
        "best_modularity": comm_results["best_modularity"],
        "nmi_tactical_alignment": align_scores["nmi"],
        "ari_tactical_alignment": align_scores["ari"]
    }

def run_community_analysis():
    """
    Run community analysis for all team-matches and save results.
    """
    team_summary_df = pd.read_parquet(PROCESSED_DIR / "team_match_summary.parquet")
    results = []
    
    print(f"Running multi-seed Louvain community detection for {len(team_summary_df)} team-matches...")
    for idx, row in team_summary_df.iterrows():
        res = analyze_team_communities(row["match_id"], row["team_name"])
        results.append(res)
        
    out_path = PROCESSED_DIR / "team_communities.parquet"
    pd.DataFrame(results).to_parquet(out_path, index=False)
    print(f"Community metrics saved to {out_path}")

if __name__ == "__main__":
    run_community_analysis()
