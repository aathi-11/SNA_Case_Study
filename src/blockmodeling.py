"""
Blockmodeling and structural equivalence module (RQ3).
Clusters players based on their network topological features to discover emergent tactical roles.
"""

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import AgglomerativeClustering

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def run_structural_equivalence_clustering(n_clusters: int = 5):
    """
    Cluster players into structural roles based on their network centrality and spatial features.
    """
    player_metrics_df = pd.read_parquet(PROCESSED_DIR / "player_network_metrics.parquet")
    
    # Feature Vector Assembly
    features = [
        "in_degree_weighted",
        "out_degree_weighted",
        "betweenness_centrality",
        "eigenvector_centrality",
        "closeness_centrality",
        "avg_x",
        "avg_y"
    ]
    
    # Drop rows with missing features
    df = player_metrics_df.dropna(subset=features).copy()
    
    if len(df) == 0:
        print("No player metrics available for clustering.")
        return None
        
    X = df[features].values
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Hierarchical Clustering (Ward linkage)
    hc = AgglomerativeClustering(n_clusters=n_clusters, linkage="ward")
    cluster_labels = hc.fit_predict(X_scaled)
    
    df["structural_role_cluster"] = cluster_labels
    
    # Cross-tabulate against nominal positions
    if "nominal_position" in df.columns and "tactical_line" in df.columns:
        crosstab = pd.crosstab(df["structural_role_cluster"], df["tactical_line"])
        print("Structural Role Clusters vs Nominal Tactical Lines:")
        print(crosstab)
        
    out_path = PROCESSED_DIR / "player_structural_roles.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Player structural roles saved to {out_path}")
    
    return df

if __name__ == "__main__":
    run_structural_equivalence_clustering()
