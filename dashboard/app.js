/**
 * Interactive Football Passing Networks & Player Impact Dashboard
 * Core Frontend Logic: Pitch Canvas Renderer, D3 Graph Network & State Manager
 */

let appData = null;
let currentCountry = "";
let currentMatchId = null;
let currentPlayer = "ALL";
let currentPassType = "ALL"; // ALL, PROG, GOAL, PRESS

// Pitch canvas dimensions (StatsBomb 120 x 80 coordinate system)
const PITCH_WIDTH = 120;
const PITCH_HEIGHT = 80;

// DOM Elements
const countrySelect = document.getElementById("country-select");
const matchSelect = document.getElementById("match-select");
const playerSelect = document.getElementById("player-select");
const toggleBtns = document.querySelectorAll(".toggle-btn");
const canvas = document.getElementById("pitch-canvas");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("pitch-tooltip");

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const response = await fetch("data/dashboard_data.json");
        appData = await response.json();
        console.log("Dashboard dataset loaded:", appData);

        populateCountrySelect();
        setupEventListeners();

        // Default selection: Argentina
        const defaultCountry = appData.countries.includes("Argentina") ? "Argentina" : appData.countries[0];
        countrySelect.value = defaultCountry;
        onCountryChange(defaultCountry);

    } catch (err) {
        console.error("Error loading dashboard data:", err);
    }
});

function populateCountrySelect() {
    countrySelect.innerHTML = "";
    appData.countries.forEach(country => {
        const opt = document.createElement("option");
        opt.value = country;
        opt.textContent = country;
        countrySelect.appendChild(opt);
    });
}

function setupEventListeners() {
    countrySelect.addEventListener("change", (e) => onCountryChange(e.target.value));
    matchSelect.addEventListener("change", (e) => onMatchChange(parseInt(e.target.value)));
    playerSelect.addEventListener("change", (e) => onPlayerChange(e.target.value));

    toggleBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            toggleBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentPassType = btn.dataset.type;
            renderPitch();
        });
    });

    // Canvas interactivity
    canvas.addEventListener("mousemove", handleCanvasHover);
    canvas.addEventListener("mouseleave", () => tooltip.classList.add("hidden"));
    canvas.addEventListener("click", handleCanvasClick);
}

function onCountryChange(country) {
    currentCountry = country;
    const matches = appData.team_matches[country] || [];

    matchSelect.innerHTML = "";
    matches.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.match_id;
        opt.textContent = `${m.label} (${m.result})`;
        matchSelect.appendChild(opt);
    });

    if (matches.length > 0) {
        currentMatchId = matches[0].match_id;
        onMatchChange(currentMatchId);
    }
}

function onMatchChange(matchId) {
    currentMatchId = matchId;
    const key = `${matchId}_${currentCountry}`;
    const details = appData.details[key];

    if (!details) return;

    // Populate player select
    playerSelect.innerHTML = '<option value="ALL">All Team Players</option>';
    details.players.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.player_name;
        opt.textContent = p.player_name + (p.is_playmaker ? " ★ (Playmaker)" : "");
        playerSelect.appendChild(opt);
    });

    currentPlayer = "ALL";
    playerSelect.value = "ALL";

    updateKPICards(details);
    updatePlayerImpactCard(null, details);
    renderPitch();
    renderD3NetworkGraph(details);
}

function onPlayerChange(playerName) {
    currentPlayer = playerName;
    const key = `${currentMatchId}_${currentCountry}`;
    const details = appData.details[key];

    if (details) {
        const playerObj = details.players.find(p => p.player_name === playerName);
        updatePlayerImpactCard(playerObj, details);
        renderPitch();
    }
}

// KPI Cards Updater
function updateKPICards(details) {
    const totalPasses = details.passes.length;
    const progPasses = details.passes.filter(p => p.is_progressive).length;
    const progPct = totalPasses > 0 ? ((progPasses / totalPasses) * 100).toFixed(1) : "0.0";
    const goalPasses = details.passes.filter(p => p.is_key_pass || p.is_goal_leading).length;

    document.getElementById("kpi-pass-count").textContent = totalPasses;
    document.getElementById("kpi-sub-pass").textContent = `Vs ${details.opponent_name} (${details.result})`;
    
    document.getElementById("kpi-prog-pct").textContent = `${progPct}%`;
    document.getElementById("kpi-prog-count").textContent = `${progPasses} progressive passes`;

    document.getElementById("kpi-goal-passes").textContent = goalPasses;

    const pmName = details.metrics.playmaker_name || "N/A";
    const pmShare = ((details.metrics.playmaker_share || 0) * 100).toFixed(1);
    document.getElementById("kpi-playmaker").textContent = pmName;
    document.getElementById("kpi-playmaker-share").textContent = `${pmShare}% Betweenness Share`;

    document.getElementById("current-match-badge").textContent = `${details.team_name} ${details.goals_for} - ${details.goals_against} ${details.opponent_name}`;
}

// Player Impact Sidebar Card
function updatePlayerImpactCard(playerObj, details) {
    const nameEl = document.getElementById("card-player-name");
    const teamEl = document.getElementById("card-player-team");
    
    const mBet = document.getElementById("m-betweenness");
    const mEig = document.getElementById("m-eigenvector");
    const mDis = document.getElementById("m-disruption");
    const mPas = document.getElementById("m-passes");

    const bBet = document.getElementById("b-betweenness");
    const bEig = document.getElementById("b-eigenvector");
    const bDis = document.getElementById("b-disruption");
    const bPas = document.getElementById("b-passes");

    if (!playerObj) {
        // Overall team playmaker summary
        const pmName = details.metrics.playmaker_name || "Team Overview";
        const topPlayer = details.players.find(p => p.player_name === pmName) || details.players[0];

        nameEl.textContent = pmName;
        teamEl.textContent = `${details.team_name} Playmaker • Select player for individual metrics`;

        if (topPlayer) {
            mBet.textContent = topPlayer.betweenness.toFixed(3);
            mEig.textContent = topPlayer.eigenvector.toFixed(3);
            mDis.textContent = `${topPlayer.disruption_power.toFixed(1)}%`;
            mPas.textContent = topPlayer.passes_made;

            bBet.style.width = `${Math.min(topPlayer.betweenness * 300, 100)}%`;
            bEig.style.width = `${Math.min(topPlayer.eigenvector * 200, 100)}%`;
            bDis.style.width = `${Math.min(topPlayer.disruption_power * 3, 100)}%`;
            bPas.style.width = `${Math.min((topPlayer.passes_made / 80) * 100, 100)}%`;
        }
    } else {
        nameEl.textContent = playerObj.player_name;
        teamEl.textContent = `${details.team_name} • ${playerObj.is_playmaker ? "Primary Playmaker" : "Squad Member"}`;

        mBet.textContent = playerObj.betweenness.toFixed(3);
        mEig.textContent = playerObj.eigenvector.toFixed(3);
        mDis.textContent = `${playerObj.disruption_power.toFixed(1)}%`;
        mPas.textContent = playerObj.passes_made;

        bBet.style.width = `${Math.min(playerObj.betweenness * 300, 100)}%`;
        bEig.style.width = `${Math.min(playerObj.eigenvector * 200, 100)}%`;
        bDis.style.width = `${Math.min(playerObj.disruption_power * 3, 100)}%`;
        bPas.style.width = `${Math.min((playerObj.passes_made / 80) * 100, 100)}%`;
    }
}

// Canvas Pitch Renderer
function renderPitch() {
    const key = `${currentMatchId}_${currentCountry}`;
    const details = appData.details[key];
    if (!details) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw Tactical Pitch Background & Lines
    drawPitchBackground();

    // Filter passes
    let passes = details.passes;
    if (currentPlayer !== "ALL") {
        passes = passes.filter(p => p.passer === currentPlayer);
    }

    if (currentPassType === "PROG") {
        passes = passes.filter(p => p.is_progressive);
    } else if (currentPassType === "GOAL") {
        passes = passes.filter(p => p.is_key_pass || p.is_goal_leading);
    } else if (currentPassType === "PRESS") {
        passes = passes.filter(p => p.under_pressure);
    }

    // Draw Pass Vectors
    passes.forEach(p => drawPassVector(p));

    // Draw Player Nodes at Average Pitch Locations
    details.players.forEach(p => {
        const isSelected = (currentPlayer === p.player_name);
        drawPlayerNode(p, isSelected);
    });
}

function scaleX(x) { return (x / PITCH_WIDTH) * canvas.width; }
function scaleY(y) { return (y / PITCH_HEIGHT) * canvas.height; }

function drawPitchBackground() {
    // Grass pitch
    ctx.fillStyle = "#0c1e2e";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Muted pitch grass stripes
    ctx.fillStyle = "rgba(255, 255, 255, 0.015)";
    const stripeWidth = canvas.width / 10;
    for (let i = 0; i < 10; i += 2) {
        ctx.fillRect(i * stripeWidth, 0, stripeWidth, canvas.height);
    }

    // Pitch Line Styling
    ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
    ctx.lineWidth = 2;

    // Outer Boundary
    ctx.strokeRect(scaleX(0), scaleY(0), scaleX(PITCH_WIDTH), scaleY(PITCH_HEIGHT));

    // Halfway Line
    ctx.beginPath();
    ctx.moveTo(scaleX(60), scaleY(0));
    ctx.lineTo(scaleX(60), scaleY(80));
    ctx.stroke();

    // Center Circle
    ctx.beginPath();
    ctx.arc(scaleX(60), scaleY(40), scaleX(10), 0, Math.PI * 2);
    ctx.stroke();

    // Penalty Areas
    // Left Box
    ctx.strokeRect(scaleX(0), scaleY(18), scaleX(18), scaleY(44));
    ctx.strokeRect(scaleX(0), scaleY(30), scaleX(6), scaleY(20));

    // Right Box
    ctx.strokeRect(scaleX(102), scaleY(18), scaleX(18), scaleY(44));
    ctx.strokeRect(scaleX(114), scaleY(30), scaleX(6), scaleY(20));
}

function drawPassVector(pass) {
    const sx = scaleX(pass.start_x);
    const sy = scaleY(pass.start_y);
    const ex = scaleX(pass.end_x);
    const ey = scaleY(pass.end_y);

    let color = "rgba(79, 172, 254, 0.35)"; // Standard pass
    let alpha = 0.35;
    let width = 1.5;

    if (pass.is_goal_leading) {
        color = "#ffb703"; // Gold
        alpha = 0.85;
        width = 3.0;
    } else if (pass.is_key_pass) {
        color = "#00f2fe"; // Cyan
        alpha = 0.75;
        width = 2.5;
    } else if (pass.is_progressive) {
        color = "#00f2fe"; // Cyan
        alpha = 0.6;
        width = 2.0;
    } else if (pass.under_pressure) {
        color = "#ef4444"; // Red
        alpha = 0.5;
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = width;

    // Draw Vector Line
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(ex, ey);
    ctx.stroke();

    // Arrow Head
    const angle = Math.atan2(ey - sy, ex - sx);
    const headLen = 7;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(ex, ey);
    ctx.lineTo(ex - headLen * Math.cos(angle - Math.PI / 6), ey - headLen * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(ex - headLen * Math.cos(angle + Math.PI / 6), ey - headLen * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fill();
}

function drawPlayerNode(player, isSelected) {
    const px = scaleX(player.avg_x);
    const py = scaleY(player.avg_y);

    // Node radius scaled by Betweenness Centrality
    const radius = 10 + Math.min(player.betweenness * 80, 20);

    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);

    if (isSelected) {
        ctx.fillStyle = "#00f2fe";
        ctx.shadowColor = "#00f2fe";
        ctx.shadowBlur = 16;
    } else if (player.is_playmaker) {
        ctx.fillStyle = "#ffb703";
        ctx.shadowColor = "#ffb703";
        ctx.shadowBlur = 10;
    } else {
        ctx.fillStyle = "#9d4edd";
        ctx.shadowBlur = 0;
    }

    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    ctx.shadowBlur = 0; // Reset shadow

    // Player Label
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(player.player_name.split(" ").pop(), px, py + radius + 14);
}

// Canvas Hover & Click Tooltip Handlers
function handleCanvasHover(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const key = `${currentMatchId}_${currentCountry}`;
    const details = appData.details[key];
    if (!details) return;

    let hoveredPlayer = null;
    details.players.forEach(p => {
        const px = scaleX(p.avg_x);
        const py = scaleY(p.avg_y);
        const dist = Math.hypot(mx - px, my - py);
        if (dist < 18) hoveredPlayer = p;
    });

    if (hoveredPlayer) {
        tooltip.innerHTML = `
            <strong>${hoveredPlayer.player_name}</strong> ${hoveredPlayer.is_playmaker ? '★' : ''}<br/>
            Passes Made: ${hoveredPlayer.passes_made}<br/>
            Betweenness Centrality: ${hoveredPlayer.betweenness.toFixed(3)}<br/>
            Disruption Power: ${hoveredPlayer.disruption_power.toFixed(1)}%
        `;
        tooltip.style.left = `${e.pageX + 15}px`;
        tooltip.style.top = `${e.pageY - 20}px`;
        tooltip.classList.remove("hidden");
    } else {
        tooltip.classList.add("hidden");
    }
}

function handleCanvasClick(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const key = `${currentMatchId}_${currentCountry}`;
    const details = appData.details[key];
    if (!details) return;

    details.players.forEach(p => {
        const px = scaleX(p.avg_x);
        const py = scaleY(p.avg_y);
        const dist = Math.hypot(mx - px, my - py);
        if (dist < 18) {
            playerSelect.value = p.player_name;
            onPlayerChange(p.player_name);
        }
    });
}

// D3 Directed Passing Network Graph Renderer
function renderD3NetworkGraph(details) {
    const container = document.getElementById("d3-network-graph");
    container.innerHTML = "";

    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select("#d3-network-graph")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    const nodes = details.players.map(p => ({
        id: p.player_name,
        betweenness: p.betweenness,
        is_playmaker: p.is_playmaker
    }));

    const links = details.edges.map(e => ({
        source: e.source,
        target: e.target,
        weight: e.weight
    }));

    const simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(links).id(d => d.id).distance(50))
        .force("charge", d3.forceManyBody().strength(-120))
        .force("center", d3.forceCenter(width / 2, height / 2));

    // Links
    const link = svg.append("g")
        .selectAll("line")
        .data(links)
        .enter().append("line")
        .attr("stroke", "rgba(79, 172, 254, 0.4)")
        .attr("stroke-width", d => Math.min(d.weight * 0.5, 4));

    // Nodes
    const node = svg.append("g")
        .selectAll("circle")
        .data(nodes)
        .enter().append("circle")
        .attr("r", d => 6 + d.betweenness * 30)
        .attr("fill", d => d.is_playmaker ? "#ffb703" : "#00f2fe")
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1.5)
        .call(d3.drag()
            .on("start", (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on("end", (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

    node.append("title").text(d => d.id);

    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node
            .attr("cx", d => d.x = Math.max(12, Math.min(width - 12, d.x)))
            .attr("cy", d => d.y = Math.max(12, Math.min(height - 12, d.y)));
    });
}
