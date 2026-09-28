"""
Weak Ties module (RQ4).
Investigates Granovetter's Strength of Weak Ties theory in chance creation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.graphs import build_team_graph
from src.communities import detect_louvain_communities
import scipy.stats as stats

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def classify_weak_ties():
    """
    Classify each pass in passing_events as intra-community (strong) or inter-community (weak).
    """
    passes_df = pd.read_parquet(PROCESSED_DIR / "passing_events.parquet")
    
    match_teams = passes_df[["match_id", "team_name"]].drop_duplicates()
    
    weak_tie_flags = []
    
    print(f"Classifying weak ties for {len(match_teams)} team-matches...")
    
    for _, row in match_teams.iterrows():
        match_id = row["match_id"]
        team_name = row["team_name"]
        
        G = build_team_graph(match_id, team_name)
        # Use 5 seeds for speed here, or default 20
        comm_res = detect_louvain_communities(G, num_seeds=5) 
        partition = comm_res["best_partition"]
        
        # Filter passes for this match-team
        mt_passes = passes_df[(passes_df["match_id"] == match_id) & (passes_df["team_name"] == team_name)]
        
        for idx, p_row in mt_passes.iterrows():
            passer = p_row["passer_name"]
            recipient = p_row["recipient_name"]
            
            comm_passer = partition.get(passer, -1)
            comm_recip = partition.get(recipient, -2)
            
            is_weak_tie = (comm_passer != comm_recip)
            weak_tie_flags.append({
                "match_id": match_id,
                "team_name": team_name,
                "passer_name": passer,
                "recipient_name": recipient,
                "period": p_row["period"],
                "minute": p_row["minute"],
                "second": p_row["second"],
                "is_weak_tie": is_weak_tie
            })
            
    wt_df = pd.DataFrame(weak_tie_flags)
    out_path = PROCESSED_DIR / "weak_ties.parquet"
    wt_df.to_parquet(out_path, index=False)
    print(f"Weak tie classifications saved to {out_path}")
    return wt_df

def compute_weak_tie_odds_ratio():
    """
    Links pre-shot sequence to pass ties to compute Weak Tie Odds Ratio.
    """
    wt_path = PROCESSED_DIR / "weak_ties.parquet"
    if not wt_path.exists():
        wt_df = classify_weak_ties()
    else:
        wt_df = pd.read_parquet(wt_path)
        
    shots_df = pd.read_parquet(PROCESSED_DIR / "shot_events.parquet")
    passes_df = pd.read_parquet(PROCESSED_DIR / "passing_events.parquet")
    
    # Merge passes with weak tie flags
    passes = pd.merge(passes_df, wt_df, on=["match_id", "team_name", "passer_name", "recipient_name", "period", "minute", "second"])
    
    pre_shot_passes = []
    
    print("Linking pre-shot sequences...")
    for _, shot in shots_df.iterrows():
        # Find passes in the same match, team, and possession
        seq_passes = passes[(passes["match_id"] == shot["match_id"]) & 
                            (passes["team_name"] == shot["team_name"]) &
                            (passes["possession"] == shot["possession"])]
        
        seq_passes = seq_passes.sort_values(by=["period", "minute", "second"])
        
        # Take the last 3 passes
        last_3 = seq_passes.tail(3)
        for _, p in last_3.iterrows():
            pre_shot_passes.append({
                "match_id": p["match_id"],
                "team_name": p["team_name"],
                "is_weak_tie": p["is_weak_tie"]
            })
            
    pre_shot_df = pd.DataFrame(pre_shot_passes)
    if pre_shot_df.empty:
        print("No pre-shot passes found.")
        return
        
    overall_weak_tie_rate = wt_df["is_weak_tie"].mean()
    preshot_weak_tie_rate = pre_shot_df["is_weak_tie"].mean()
    
    print(f"Overall Weak Tie Rate: {overall_weak_tie_rate:.2%}")
    print(f"Pre-Shot Weak Tie Rate: {preshot_weak_tie_rate:.2%}")
    
    # Odds Ratio
    odds_preshot = preshot_weak_tie_rate / (1 - preshot_weak_tie_rate) if preshot_weak_tie_rate < 1 else np.inf
    odds_overall = overall_weak_tie_rate / (1 - overall_weak_tie_rate) if overall_weak_tie_rate < 1 else np.inf
    or_val = odds_preshot / odds_overall if odds_overall > 0 else np.nan
    
    print(f"Odds Ratio (Weak Tie | Pre-Shot): {or_val:.2f}")
    
    # Fisher Exact Test
    a = int(pre_shot_df["is_weak_tie"].sum())
    b = len(pre_shot_df) - a
    c = int(wt_df["is_weak_tie"].sum()) - a
    d = len(wt_df) - len(pre_shot_df) - c
    
    _, p_val = stats.fisher_exact([[a, b], [c, d]])
    print(f"Fisher Exact Test p-value: {p_val:.4f}")

if __name__ == "__main__":
    compute_weak_tie_odds_ratio()
