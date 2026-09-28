"""
Cross-match comparisons module for Football Passing Networks.
Framework 2: Longitudinal tournament progression across stages.
Framework 5: Opponent-Adjusted Deviation Analysis (Network Disruption Index).
"""

from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def compute_longitudinal_stages():
    """
    Aggregate metrics per team across match stages (1->5) and export.
    """
    metrics_df = pd.read_parquet(PROCESSED_DIR / "team_network_metrics.parquet")
    summary_df = pd.read_parquet(PROCESSED_DIR / "team_match_summary.parquet")
    
    if "stage_name" not in summary_df.columns:
        print("Warning: stage_name not found in summary_df. Make sure to run data_prep.py first.")
        return None
        
    # Merge stage info safely avoiding duplicate columns
    cols_to_use = ["match_id", "team_name"] + [c for c in ["stage_name", "stage_order"] if c not in metrics_df.columns]
    df = pd.merge(metrics_df, summary_df[cols_to_use], on=["match_id", "team_name"])
    
    # Sort by team and stage
    df = df.sort_values(by=["team_name", "stage_order"])
    
    out_path = PROCESSED_DIR / "longitudinal_stages.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Longitudinal stage trends saved to {out_path}")
    return df

def compute_disruption_index():
    """
    Calculate baseline tournament averages for every team.
    For each match, compute Disruption(T_A | T_B) = M(T_A, vs T_B) - M_bar(T_A)
    Average across matches to compute Average Defensive Disruption Power.
    """
    metrics_df = pd.read_parquet(PROCESSED_DIR / "team_network_metrics.parquet")
    summary_df = pd.read_parquet(PROCESSED_DIR / "team_match_summary.parquet")
    # Merge required columns safely to avoid suffixes
    cols_to_use = ["match_id", "team_name"] + [c for c in ["opponent_name", "progressive_pass_ratio"] if c not in metrics_df.columns]
    df = pd.merge(metrics_df, summary_df[cols_to_use], on=["match_id", "team_name"])
    
    # Target metrics to analyze for disruption
    target_metrics = ["density", "global_efficiency", "progressive_pass_ratio", "playmaker_share"]
    
    # Compute baselines
    baselines = df.groupby("team_name")[target_metrics].mean().reset_index()
    baselines = baselines.rename(columns={m: f"baseline_{m}" for m in target_metrics})
    
    df = pd.merge(df, baselines, on="team_name")
    
    # Compute disruption (Difference from baseline)
    for m in target_metrics:
        # Negative disruption means the opponent reduced the metric
        df[f"disruption_{m}"] = df[m] - df[f"baseline_{m}"]
        
    # Aggregate opponent disruption power
    opp_disruption = df.groupby("opponent_name")[[f"disruption_{m}" for m in target_metrics]].mean().reset_index()
    opp_disruption = opp_disruption.rename(columns={"opponent_name": "team_name"})
    
    out_path = PROCESSED_DIR / "disruption_power.parquet"
    opp_disruption.to_parquet(out_path, index=False)
    print(f"Opponent Disruption Indices saved to {out_path}")
    return opp_disruption

if __name__ == "__main__":
    compute_longitudinal_stages()
    compute_disruption_index()
