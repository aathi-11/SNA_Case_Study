"""
Data preparation module for Football Passing Networks Case Study using StatsBomb Open Data.
Fetches, cleans, truncates (at first sub/red card), and extracts network edge lists and team-level metrics.
"""

import os
import json
import urllib.request
import pandas as pd
import numpy as np
from pathlib import Path
import time


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
EVENTS_DIR = RAW_DIR / "events"
PROCESSED_DIR = DATA_DIR / "processed"

# Target competitions: FIFA World Cup 2018 (43, 3) and 2022 (43, 106)
TARGET_COMPETITIONS = [
    {"competition_id": 43, "season_id": 3, "season_name": "2018"},
    {"competition_id": 43, "season_id": 106, "season_name": "2022"},
]

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def fetch_json(url: str, max_retries: int = 3, delay: float = 0.5) -> dict:
    """Fetch JSON from a URL with retries."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to fetch {url}: {e}")
            time.sleep(delay * (attempt + 1))


def download_raw_data(force: bool = False) -> list:
    """
    Download raw match metadata and event files from StatsBomb open data.
    Saves match metadata and raw JSON event logs.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    matches_list = []
    print("Fetching competition matches metadata...")
    for comp in TARGET_COMPETITIONS:
        comp_id = comp["competition_id"]
        season_id = comp["season_id"]
        season_name = comp["season_name"]
        
        matches_url = f"{BASE_URL}/matches/{comp_id}/{season_id}.json"
        raw_matches = fetch_json(matches_url)
        
        for m in raw_matches:
            home = m["home_team"]["home_team_name"]
            away = m["away_team"]["away_team_name"]
            h_score = m["home_score"]
            a_score = m["away_score"]
            
            # Regulation/Match Outcome
            if h_score > a_score:
                home_outcome, away_outcome = "Win", "Loss"
            elif a_score > h_score:
                home_outcome, away_outcome = "Loss", "Win"
            else:
                home_outcome, away_outcome = "Draw", "Draw"
                
            matches_list.append({
                "match_id": m["match_id"],
                "match_date": m["match_date"],
                "competition_id": comp_id,
                "season_id": season_id,
                "competition_name": "FIFA World Cup",
                "season_name": season_name,
                "home_team_id": m["home_team"]["home_team_id"],
                "home_team": home,
                "away_team_id": m["away_team"]["away_team_id"],
                "away_team": away,
                "home_score": h_score,
                "away_score": a_score,
                "home_outcome": home_outcome,
                "away_outcome": away_outcome,
                "stadium": m.get("stadium", {}).get("name", "Unknown") if isinstance(m.get("stadium"), dict) else "Unknown",
            })
            
    matches_df = pd.DataFrame(matches_list)
    matches_parquet = RAW_DIR / "matches.parquet"
    matches_df.to_parquet(matches_parquet, index=False)
    print(f"Saved match metadata for {len(matches_df)} matches to {matches_parquet}")

    # Download event files
    total_matches = len(matches_df)
    print(f"Downloading raw event files for {total_matches} matches...")
    for idx, match_id in enumerate(matches_df["match_id"], 1):
        event_path = EVENTS_DIR / f"{match_id}.json"
        if force or not event_path.exists():
            event_url = f"{BASE_URL}/events/{match_id}.json"
            try:
                events = fetch_json(event_url)
                with open(event_path, "w", encoding="utf-8") as f:
                    json.dump(events, f)
            except Exception as e:
                print(f"Error downloading events for match {match_id}: {e}")
        if idx % 20 == 0 or idx == total_matches:
            print(f"  Progress: {idx}/{total_matches} matches fetched.")
            
    return matches_list


def get_first_sub_or_red_card_time(events: list) -> dict:
    """
    Find the timestamp (period, minute, second) of the first substitution or red card for each team.
    """
    cutoff_times = {}
    
    for e in events:
        team_name = e.get("team", {}).get("name")
        if not team_name:
            continue
            
        is_sub = (e.get("type", {}).get("name") == "Substitution")
        
        foul_card = e.get("foul_committed", {}).get("card", {}).get("name", "")
        bad_card = e.get("bad_behaviour", {}).get("card", {}).get("name", "")
        is_red = (foul_card in ["Red Card", "Second Yellow"]) or (bad_card in ["Red Card", "Second Yellow"])
        
        if is_sub or is_red:
            period = e.get("period", 1)
            minute = e.get("minute", 90)
            second = e.get("second", 0)
            time_tuple = (period, minute, second)
            
            if team_name not in cutoff_times:
                cutoff_times[team_name] = time_tuple
            else:
                cutoff_times[team_name] = min(cutoff_times[team_name], time_tuple)
                
    return cutoff_times


def is_before_cutoff(period: int, minute: int, second: int, cutoff: tuple) -> bool:
    """Check if event timestamp (period, minute, second) occurs strictly before cutoff tuple."""
    if cutoff is None:
        return True
    return (period, minute, second) < cutoff


def process_dataset():
    """
    Process raw match and event files:
    1. Truncate passes at team's 1st sub/red card.
    2. Extract completed passes, positions, edge lists, player stats, and team summary.
    3. Save outputs to data/processed/.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches_parquet = RAW_DIR / "matches.parquet"
    if not matches_parquet.exists():
        download_raw_data()
        
    matches_df = pd.read_parquet(matches_parquet)
    
    processed_passes = []
    edges_list = []
    player_stats_list = []
    team_summaries = []
    
    print(f"Processing event logs for {len(matches_df)} matches...")
    
    for idx, match_row in matches_df.iterrows():
        match_id = match_row["match_id"]
        event_path = EVENTS_DIR / f"{match_id}.json"
        
        if not event_path.exists():
            continue
            
        with open(event_path, "r", encoding="utf-8") as f:
            events = json.load(f)
            
        cutoff_times = get_first_sub_or_red_card_time(events)
        
        # Process teams in this match
        for team_name, outcome, score, opp_name, opp_score in [
            (match_row["home_team"], match_row["home_outcome"], match_row["home_score"], match_row["away_team"], match_row["away_score"]),
            (match_row["away_team"], match_row["away_outcome"], match_row["away_score"], match_row["home_team"], match_row["home_score"]),
        ]:
            cutoff = cutoff_times.get(team_name, None)
            first_sub_min = cutoff[1] if cutoff else 90
            
            # Extract passes for this team
            team_passes = []
            all_team_passes_count = 0
            total_duration = 0.0
            
            for e in events:
                if e.get("team", {}).get("name") != team_name:
                    continue
                    
                if e.get("type", {}).get("name") == "Pass":
                    all_team_passes_count += 1
                    
                    # Completed pass filter (pass.outcome is None/NaN)
                    pass_info = e.get("pass", {})
                    if "outcome" not in pass_info:
                        period = e.get("period", 1)
                        minute = e.get("minute", 0)
                        second = e.get("second", 0)
                        
                        # Truncate at cutoff for stable lineup
                        if is_before_cutoff(period, minute, second, cutoff):
                            player_name = e.get("player", {}).get("name")
                            player_id = e.get("player", {}).get("id")
                            recip_name = pass_info.get("recipient", {}).get("name")
                            recip_id = pass_info.get("recipient", {}).get("id")
                            
                            if player_name and recip_name:
                                loc = e.get("location", [np.nan, np.nan])
                                end_loc = pass_info.get("end_location", [np.nan, np.nan])
                                length = pass_info.get("length", 0.0)
                                angle = pass_info.get("angle", 0.0)
                                is_prog = (end_loc[0] - loc[0] > 10.0) if (len(end_loc) >= 2 and len(loc) >= 2) else False
                                
                                pass_dict = {
                                    "match_id": match_id,
                                    "competition_name": match_row["competition_name"],
                                    "season_name": match_row["season_name"],
                                    "team_name": team_name,
                                    "period": period,
                                    "minute": minute,
                                    "second": second,
                                    "passer_id": player_id,
                                    "passer_name": player_name,
                                    "recipient_id": recip_id,
                                    "recipient_name": recip_name,
                                    "start_x": loc[0],
                                    "start_y": loc[1],
                                    "end_x": end_loc[0],
                                    "end_y": end_loc[1],
                                    "length": length,
                                    "angle": angle,
                                    "is_progressive": is_prog,
                                    "under_pressure": e.get("under_pressure", False),
                                }
                                team_passes.append(pass_dict)
                                processed_passes.append(pass_dict)

            # Compute edge lists for this team-match
            df_tp = pd.DataFrame(team_passes)
            if not df_tp.empty:
                # Directed passing pairs
                grouped_edges = df_tp.groupby(
                    ["passer_id", "passer_name", "recipient_id", "recipient_name"]
                ).agg(
                    weight=("length", "count"),
                    avg_distance=("length", "mean"),
                    progressive_passes=("is_progressive", "sum")
                ).reset_index()
                
                for _, erow in grouped_edges.iterrows():
                    edges_list.append({
                        "match_id": match_id,
                        "competition_name": match_row["competition_name"],
                        "season_name": match_row["season_name"],
                        "team_name": team_name,
                        "passer_id": erow["passer_id"],
                        "passer_name": erow["passer_name"],
                        "recipient_id": erow["recipient_id"],
                        "recipient_name": erow["recipient_name"],
                        "weight": erow["weight"],
                        "avg_distance": erow["avg_distance"],
                        "progressive_passes": erow["progressive_passes"],
                    })
                    
                # Player level position and pass stats
                passers = df_tp.groupby(["passer_id", "passer_name"]).agg(
                    avg_x=("start_x", "mean"),
                    avg_y=("start_y", "mean"),
                    passes_made=("start_x", "count")
                ).reset_index().rename(columns={"passer_id": "player_id", "passer_name": "player_name"})
                
                recips = df_tp.groupby(["recipient_id", "recipient_name"]).agg(
                    passes_received=("start_x", "count")
                ).reset_index().rename(columns={"recipient_id": "player_id", "recipient_name": "player_name"})
                
                players_df = pd.merge(passers, recips, on=["player_id", "player_name"], how="outer").fillna(0)
                for _, prow in players_df.iterrows():
                    player_stats_list.append({
                        "match_id": match_id,
                        "team_name": team_name,
                        "player_id": prow["player_id"],
                        "player_name": prow["player_name"],
                        "avg_x": prow["avg_x"],
                        "avg_y": prow["avg_y"],
                        "passes_made": int(prow["passes_made"]),
                        "passes_received": int(prow["passes_received"]),
                    })

                # Team match style and outcome summary
                truncated_count = len(df_tp)
                avg_len = df_tp["length"].mean() if truncated_count > 0 else 0.0
                prog_count = df_tp["is_progressive"].sum()
                prog_ratio = prog_count / truncated_count if truncated_count > 0 else 0.0
            else:
                truncated_count = 0
                avg_len = 0.0
                prog_ratio = 0.0

            team_summaries.append({
                "match_id": match_id,
                "competition_name": match_row["competition_name"],
                "season_name": match_row["season_name"],
                "team_name": team_name,
                "opponent_name": opp_name,
                "result": outcome,
                "goals_for": score,
                "goals_against": opp_score,
                "truncated_pass_count": truncated_count,
                "avg_pass_length": avg_len,
                "progressive_pass_ratio": prog_ratio,
                "first_sub_minute": first_sub_min,
            })
            
    # Save all processed dataframes to parquet
    print("Saving processed Parquet datasets...")
    
    passes_parquet = PROCESSED_DIR / "passing_events.parquet"
    pd.DataFrame(processed_passes).to_parquet(passes_parquet, index=False)
    print(f"  - Cleaned passing events: {passes_parquet} ({len(processed_passes)} rows)")

    edges_parquet = PROCESSED_DIR / "passing_edges.parquet"
    pd.DataFrame(edges_list).to_parquet(edges_parquet, index=False)
    print(f"  - Network edges: {edges_parquet} ({len(edges_list)} edges)")

    player_stats_parquet = PROCESSED_DIR / "player_match_stats.parquet"
    pd.DataFrame(player_stats_list).to_parquet(player_stats_parquet, index=False)
    print(f"  - Player match stats & pitch positions: {player_stats_parquet} ({len(player_stats_list)} rows)")

    team_summary_parquet = PROCESSED_DIR / "team_match_summary.parquet"
    pd.DataFrame(team_summaries).to_parquet(team_summary_parquet, index=False)
    print(f"  - Team match summaries & playing style: {team_summary_parquet} ({len(team_summaries)} team-matches)")

    print("\nDataset preparation completed successfully!")


if __name__ == "__main__":
    download_raw_data()
    process_dataset()
