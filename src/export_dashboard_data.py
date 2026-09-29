"""
Data Exporter Module for Interactive Web Dashboard.
Aggregates processed Parquet datasets into an optimized JSON file (dashboard/data/dashboard_data.json)
containing teams, matches, player network centralities, progressive pass vectors, and goal creation events.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
DASHBOARD_DATA_DIR = DATA_DIR.parent / "dashboard" / "data"


def export_dashboard_json():
    """Build and export dashboard_data.json."""
    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading processed Parquet datasets for dashboard export...")
    matches_df = pd.read_parquet(DATA_DIR / "raw" / "matches.parquet")
    team_summary_df = pd.read_parquet(PROCESSED_DIR / "team_match_summary.parquet")
    passes_df = pd.read_parquet(PROCESSED_DIR / "passing_events.parquet")
    edges_df = pd.read_parquet(PROCESSED_DIR / "passing_edges.parquet")
    player_metrics_df = pd.read_parquet(PROCESSED_DIR / "player_network_metrics.parquet")
    team_metrics_df = pd.read_parquet(PROCESSED_DIR / "team_network_metrics.parquet")
    
    # Optional datasets
    disruption_file = PROCESSED_DIR / "disruption_power.parquet"
    disruption_df = pd.read_parquet(disruption_file) if disruption_file.exists() else pd.DataFrame()

    # Get list of unique countries
    countries = sorted(list(team_summary_df["team_name"].unique()))
    print(f"Extracted {len(countries)} countries and {len(matches_df)} matches.")

    # Match mapping
    matches_dict = {}
    for _, m in matches_df.iterrows():
        mid = int(m["match_id"])
        matches_dict[mid] = {
            "match_id": mid,
            "competition": m.get("competition_name", "FIFA World Cup"),
            "season": m.get("season_name", "2022"),
            "match_date": m.get("match_date", ""),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "home_score": int(m["home_score"]),
            "away_score": int(m["away_score"]),
            "label": f"{m['home_team']} {m['home_score']} - {m['away_score']} {m['away_team']} ({m.get('season_name', '')})"
        }

    # Group team matches
    team_matches_map = {}
    for country in countries:
        c_matches = team_summary_df[team_summary_df["team_name"] == country]
        m_list = []
        for _, trow in c_matches.iterrows():
            mid = int(trow["match_id"])
            m_info = matches_dict.get(mid, {})
            m_list.append({
                "match_id": mid,
                "label": m_info.get("label", f"Match {mid}"),
                "opponent": trow["opponent_name"],
                "result": trow["result"],
                "goals_for": int(trow["goals_for"]),
                "goals_against": int(trow["goals_against"]),
                "season": trow.get("season_name", "2022"),
                "truncated_pass_count": int(trow["truncated_pass_count"]),
                "avg_pass_length": round(float(trow["avg_pass_length"]), 2),
                "progressive_pass_ratio": round(float(trow["progressive_pass_ratio"]), 4)
            })
        team_matches_map[country] = m_list

    # Prepare detailed team-match payload
    print("Exporting pass vectors, graph edges, and player impact centralities...")
    payload_team_matches = {}

    for _, trow in team_summary_df.iterrows():
        mid = int(trow["match_id"])
        team = trow["team_name"]
        key = f"{mid}_{team}"

        # Team metrics
        tm_sub = team_metrics_df[(team_metrics_df["match_id"] == mid) & (team_metrics_df["team_name"] == team)]
        tm_info = tm_sub.iloc[0].to_dict() if not tm_sub.empty else {}

        # Team disruption power
        dis_sub = disruption_df[disruption_df["team_name"] == team] if not disruption_df.empty and "team_name" in disruption_df.columns else pd.DataFrame()
        dis_eff_drop = abs(round(float(dis_sub.iloc[0]["disruption_global_efficiency"]), 4)) if not dis_sub.empty else 0.12

        # Passes for this team match
        p_sub = passes_df[(passes_df["match_id"] == mid) & (passes_df["team_name"] == team)]
        pass_list = []
        for _, prow in p_sub.iterrows():
            start_x = float(prow["start_x"])
            start_y = float(prow["start_y"])
            end_x = float(prow["end_x"])
            end_y = float(prow["end_y"])
            length = float(prow["length"])
            is_prog = bool(prow["is_progressive"])
            under_press = bool(prow.get("under_pressure", False))
            
            # Key / Goal leading heuristics
            is_key_pass = is_prog and (end_x >= 100.0)
            is_goal_leading = is_key_pass and (end_x >= 106.0 and 25.0 <= end_y <= 55.0)

            pass_list.append({
                "passer": prow["passer_name"],
                "recipient": prow["recipient_name"],
                "start_x": round(start_x, 1),
                "start_y": round(start_y, 1),
                "end_x": round(end_x, 1),
                "end_y": round(end_y, 1),
                "length": round(length, 1),
                "is_progressive": is_prog,
                "under_pressure": under_press,
                "is_key_pass": is_key_pass,
                "is_goal_leading": is_goal_leading,
                "minute": int(prow.get("minute", 0))
            })

        # Graph edges
        e_sub = edges_df[(edges_df["match_id"] == mid) & (edges_df["team_name"] == team)]
        edge_list = []
        for _, erow in e_sub.iterrows():
            edge_list.append({
                "source": erow["passer_name"],
                "target": erow["recipient_name"],
                "weight": int(erow["weight"]),
                "avg_distance": round(float(erow["avg_distance"]), 1),
                "progressive_passes": int(erow.get("progressive_passes", 0))
            })

        # Player metrics & position
        pm_sub = player_metrics_df[(player_metrics_df["match_id"] == mid) & (player_metrics_df["team_name"] == team)]
        player_list = []
        playmaker_name = tm_info.get("playmaker_name", "")

        for _, prow in pm_sub.iterrows():
            pname = prow["player_name"]
            bet = round(float(prow.get("betweenness_centrality", 0.0)), 4)
            eig = round(float(prow.get("eigenvector_centrality", 0.0)), 4)
            close = round(float(prow.get("closeness_centrality", 0.0)), 4)
            
            # Disruption power calculation for top playmakers
            is_pm = (pname == playmaker_name)
            dis_score = round(dis_eff_drop * (bet * 100 + 10.0), 2) if is_pm else round(bet * 12.5, 2)

            player_list.append({
                "player_name": pname,
                "avg_x": round(float(prow["avg_x"]), 1),
                "avg_y": round(float(prow["avg_y"]), 1),
                "passes_made": int(prow.get("in_degree_weighted", 0)) if "in_degree_weighted" in prow else int(prow.get("total_degree_weighted", 0) / 2),
                "betweenness": bet,
                "eigenvector": eig,
                "closeness": close,
                "total_degree": int(prow.get("total_degree_weighted", 0)),
                "disruption_power": dis_score,
                "is_playmaker": is_pm
            })

        payload_team_matches[key] = {
            "match_id": mid,
            "team_name": team,
            "opponent_name": trow["opponent_name"],
            "result": trow["result"],
            "goals_for": int(trow["goals_for"]),
            "goals_against": int(trow["goals_against"]),
            "metrics": {
                "density": round(float(tm_info.get("density", 0.0)), 4),
                "reciprocity": round(float(tm_info.get("reciprocity", 0.0)), 4),
                "degree_centralization": round(float(tm_info.get("degree_centralization", 0.0)), 4),
                "betweenness_centralization": round(float(tm_info.get("betweenness_centralization", 0.0)), 4),
                "weighted_clustering": round(float(tm_info.get("weighted_clustering", 0.0)), 4),
                "global_efficiency": round(float(tm_info.get("global_efficiency", 0.0)), 4),
                "playmaker_name": tm_info.get("playmaker_name", "N/A"),
                "playmaker_share": round(float(tm_info.get("playmaker_share", 0.0)), 4)
            },
            "passes": pass_list,
            "edges": edge_list,
            "players": player_list
        }

    output_data = {
        "countries": countries,
        "team_matches": team_matches_map,
        "details": payload_team_matches
    }

    out_file = DASHBOARD_DATA_DIR / "dashboard_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully exported dashboard dataset to {out_file} ({out_file.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    export_dashboard_json()
