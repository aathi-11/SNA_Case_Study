"""
Scouting module for Football Passing Networks.
Generates automated opposition dossier identifying tactical weak points.
"""

from pathlib import Path
import pandas as pd
from src.graphs import build_team_graph
from src.metrics import compute_node_removal_vulnerability
from src.communities import detect_louvain_communities
import networkx as nx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
REPORT_DIR = DATA_DIR.parent / "report"

def generate_scouting_report(match_id: int, team_name: str, out_file: Path = None):
    """
    Generate an opposition dossier based on network topology.
    """
    G = build_team_graph(match_id, team_name)
    vuln_dict = compute_node_removal_vulnerability(G)
    
    if not vuln_dict:
        return "No passing data available for this team."
        
    # Find key playmaker (highest betweenness)
    try:
        bet = nx.betweenness_centrality(G, weight="distance", normalized=True)
    except:
        bet = {}
    
    top_playmaker = max(bet, key=bet.get) if bet else "None"
    
    # Node-removal fragility ranking
    df_vuln = pd.DataFrame.from_dict(vuln_dict, orient='index').reset_index()
    df_vuln.columns = ["player", "efficiency_drop_pct", "subgraph_efficiency"]
    df_vuln = df_vuln.sort_values(by="efficiency_drop_pct", ascending=False)
    
    if df_vuln.empty:
        return "Not enough data."
        
    top_spof = df_vuln.iloc[0]["player"]
    spof_drop = df_vuln.iloc[0]["efficiency_drop_pct"]
    
    # Communities
    comm_res = detect_louvain_communities(G, num_seeds=5)
    
    md_content = f"# Opposition Tactical Dossier: {team_name}\n\n"
    
    md_content += f"## 1. Network Centrality & Playmaker Dependency\n"
    md_content += f"- **Primary Hub**: {top_playmaker} holds the highest betweenness centrality.\n"
    
    md_content += f"## 2. Structural Fragility & SPOF\n"
    if spof_drop > 25.0:
        md_content += f"- **CRITICAL VULNERABILITY**: Removing {top_spof} drops network efficiency by {spof_drop:.1f}%.\n"
        md_content += f"  - *Recommendation*: Implement man-marking or heavy pressing on {top_spof} to disconnect the team.\n"
    else:
        md_content += f"- **Distributed Structure**: The network is highly redundant. Maximum efficiency drop is {spof_drop:.1f}% ({top_spof}).\n"
        md_content += f"  - *Recommendation*: Team circulation cannot be shut down by isolating a single player; use zonal pressing.\n"
        
    md_content += f"\n## 3. Top Fragility Ranking\n"
    for i, row in df_vuln.head(3).iterrows():
        md_content += f"{i+1}. {row['player']} ({row['efficiency_drop_pct']:.1f}% drop)\n"
        
    md_content += f"\n## 4. Community Structure\n"
    md_content += f"The team's passing breaks down into distinct functional sub-units (modularity {comm_res['best_modularity']:.2f}).\n"
    
    if out_file:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w") as f:
            f.write(md_content)
        print(f"Scouting report generated: {out_file}")
        
    return md_content
