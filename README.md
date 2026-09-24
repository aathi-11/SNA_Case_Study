# Football Passing Networks: Structure, Outcomes and Playing Style

Social Network Analysis case study using StatsBomb Open Data.

## 1. Project Overview

**Research question:** Do network structure metrics (density, centralization, betweenness of the playmaker) differ between winning and losing teams, or between playing styles?

**Real-world use:** Scouting and opposition analysis, i.e. finding who a team's passing structure depends on and how to disrupt it.

**Data:** [StatsBomb Open Data](https://github.com/statsbomb/open-data) (FIFA World Cup 2018 and 2022, optionally Euro 2020). Free, citable, and attribution to StatsBomb is required.

**Methods:**
- Weighted, directed passing graphs
- Betweenness and eigenvector centrality
- Louvain community detection (tactical sub-units)
- Pitch-overlay visualizations
- Non-parametric tests and logistic regression

---

## 2. Suggested Repository Structure

```
football-passing-networks/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/            # cached StatsBomb events (parquet)
│   └── processed/      # graph objects, metric tables
├── notebooks/
│   ├── 01_data_pull.ipynb
│   ├── 02_build_graphs.ipynb
│   ├── 03_metrics.ipynb
│   ├── 04_communities.ipynb
│   ├── 05_statistics.ipynb
│   └── 06_visualizations.ipynb
├── src/
│   ├── graphs.py       # graph construction
│   ├── metrics.py      # team- and player-level metrics
│   └── plots.py        # mplsoccer helpers
└── report/
```

**Setup**

```bash
pip install statsbombpy networkx pandas numpy scipy statsmodels scikit-learn mplsoccer matplotlib pyarrow
```

---

## 3. Step-by-Step Walkthrough

### Step 1: Lock the scope

Make these decisions first; they become your Methodology section.

| Decision | Choice |
|---|---|
| Sample | World Cup 2018 + 2022 (about 128 matches, about 256 team-match graphs) |
| Outcome | Winner vs loser at end of regulation time; drop draws (or analyse as a third group) |
| Playing style | Measurable variables: possession share, passes per possession, average pass length, progression toward goal. Cluster teams (k-means) or split into terciles |
| Nodes | Players, using only passes up to the team's first substitution or red card so the lineup is stable |
| Edges | Directed passer → recipient, weighted by completed pass count |

### Step 2: Pull and clean the data

```python
from statsbombpy import sb

# Verify competition/season IDs first
print(sb.competitions())

matches = sb.matches(competition_id=43, season_id=3)   # World Cup 2018 (check IDs)
events = sb.events(match_id=match_id)

passes = events[(events["type"] == "Pass") & (events["pass_outcome"].isna())]  # completed passes only
```

- Truncate each team's passes at its first substitution or red card.
- Keep the pass start location (used for pitch plots).
- Cache everything to parquet to avoid re-downloading.
- Cite StatsBomb according to its attribution terms.

### Step 3: Build the graphs

One `nx.DiGraph` per team per match.

```python
import networkx as nx

G = nx.DiGraph()
for (passer, recipient), w in pass_counts.items():
    G.add_edge(passer, recipient, weight=w, distance=1.0 / w)
```

Use `distance = 1/weight` for path-based measures such as betweenness. Weights are pass strengths, but shortest-path algorithms treat weights as costs. Justify this choice in the report.

### Step 4: Compute the metrics

**Team-level (win/loss and style comparisons)**

| Metric | Why |
|---|---|
| Density | Overall connectedness of passing |
| Degree centralization (Freeman) | Is passing spread out or funnelled through a few players? |
| Betweenness centralization | Dependence on brokers |
| Reciprocity | Two-way passing relationships |
| Weighted clustering coefficient | Local passing triangles |
| Global efficiency | How easily the ball can move between any two players |

**Player-level (playmaker analysis)**
- Weighted betweenness (use `distance`).
- Eigenvector centrality via `eigenvector_centrality_numpy`, cross-checked with PageRank, since standard eigenvector centrality can fail to converge on directed graphs.
- Playmaker dependence: the top player's share of team betweenness.

> **Confound warning:** more passes mechanically produce a denser graph. Normalize by total passes or control for possession in the models.

### Step 5: Communities (Louvain)

```python
communities = nx.community.louvain_communities(G_undirected, weight="weight", seed=42)
modularity = nx.community.modularity(G_undirected, communities, weight="weight")
```

- Run on the undirected weighted projection (Louvain does not natively handle direction).
- Louvain is stochastic: run about 20 seeds and report the modularity distribution.
- Compare communities with positional lines (defence/midfield/attack) using NMI or ARI. This shows whether passing sub-units follow the formation or cut across it.

### Step 6: Statistical testing

- **Win vs loss:** Wilcoxon signed-rank test (both teams in a match are paired), plus effect sizes.
- **Style groups:** Kruskal-Wallis with post-hoc tests.
- **Confound control:** Logistic regression, e.g. `win ~ density + centralization + playmaker_share + possession`.
- **Multiple comparisons:** Holm correction.
- **Framing:** These are associations, not causal claims.

### Step 7: Visualizations

Use `mplsoccer` for pitch overlays.

- Nodes at each player's average pass location, sized by betweenness.
- Edge width by pass count.
- Node colour by Louvain community.
- Two contrasting cases side by side (e.g. possession-based vs direct).
- Box plots: winners vs losers per metric; style-group comparisons.
- Every figure gets a caption that explains what it shows.

### Step 8: Scouting application

Choose one team and write a short opposition report:
- Identify the playmaker and the community structure.
- **Vulnerability test:** remove the top-betweenness player from the graph and measure the drop in global efficiency. A large drop means the team relies heavily on that player.

### Step 9: Write the report

Map each section to the rubric (each criterion is scored out of 10).

| Rubric criterion | What to include |
|---|---|
| Introduction & Context | Research question, why SNA fits passing data, scouting relevance |
| Network Data Collection & Sources | StatsBomb Open Data, why it is credible, filtering rules, node/edge definitions |
| Network Modeling & Methodology | Justify every metric, the `1/weight` distance choice, Louvain and how instability is handled |
| Analysis & Interpretation | Test results, effect sizes, possession confound, tactical meaning of the numbers |
| Visualization & Graph Representation | Pitch overlays, box plots, community colouring, captioned figures |
| Discussion & Implications | Scouting use, removal experiment, limitations, future work |
| Conclusion & Summary | Key findings and contribution |
| Overall Clarity & Presentation | Consistent structure, labelled figures, a short methods flowchart |

**What moves the report into the top band:** justify every method choice, and go beyond description with the statistical tests, the confound control and the removal experiment.

---

## 4. Limitations to State Explicitly

- Association, not causation; the tournament sample is limited.
- Passing networks capture only completed passes, not off-ball movement or defensive actions.
- Stronger teams both pass more and win more, so quality and possession are confounds.
- Louvain results depend on random initialisation.
- Truncating at the first substitution reduces the number of passes per graph.

## 5. Possible Extensions

- Weight edges by expected threat (xT) instead of raw pass counts.
- Temporal networks (compare 0-30, 30-60, 60-90 minute windows).
- Compare results across tournaments (World Cup vs Euros).
- Predict match outcome from network features.

## 6. Data Attribution

Data provided by [StatsBomb](https://statsbomb.com). Follow the attribution requirements in the open-data repository's licence and user agreement.
