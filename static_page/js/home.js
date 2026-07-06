// Home dashboard: metrics, daily games with quarter boxscores, searchable totals table.
(async function () {
  let data;
  try {
    data = await NBA.loadJSON("data/home.json");
  } catch (e) {
    document.getElementById("game-list").innerHTML =
      `<div class="alert alert-danger status-empty">Could not load dashboard data.</div>`;
    return;
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---- Metrics ----
  const m = data.metrics || {};
  document.getElementById("m-games").textContent = m.game_count ?? 0;
  document.getElementById("m-players").textContent = m.player_count ?? 0;
  document.getElementById("m-teams").textContent = m.team_count ?? 0;
  if (m.top_scorer) {
    document.getElementById("m-top-scorer").textContent = m.top_scorer.Player ?? "-";
    document.getElementById("m-top-scorer-note").textContent =
      `${Math.round(m.top_scorer.PTS ?? 0)} season points`;
  }
  if (data.latest_game_date) {
    document.getElementById("games-date").textContent = data.latest_game_date;
  }

  // ---- Daily games (pair rows, attach quarter boxscore) ----
  const games = data.games || [];
  const boxscores = data.boxscores || [];
  const boxByTeam = {};
  boxscores.forEach((b) => (boxByTeam[b.team] = b));
  const otKeys = ["OT", "2OT", "3OT"];
  const gameList = document.getElementById("game-list");

  if (!games.length) {
    gameList.innerHTML = `<div class="alert alert-warning status-empty">No NBA games data is available yet.</div>`;
  } else {
    const cards = [];
    for (let i = 0; i < games.length; i += 2) {
      const g1 = games[i];
      const g2 = games[i + 1] || null;
      const s1 = g1.score ?? 0;
      const s2 = g2 ? g2.score ?? 0 : 0;
      const winner = !g2 || s1 >= s2 ? g1 : g2;
      const loser = g2 ? (s1 >= s2 ? g2 : g1) : null;

      const teamRow = (t, isLoser) => t ? `
        <div class="team-row${isLoser ? " is-loser" : ""}">
          <img src="img/${esc(t.team_logo || "nba.svg")}" alt="${esc(t.team)} logo" class="team-logo">
          <div class="team-name">${esc(t.team)}</div>
          <div class="team-score">${esc(t.score)}</div>
        </div>` : "";

      const activeOT = otKeys.filter((k) =>
        [winner, loser].some((t) => t && boxByTeam[t.team] && boxByTeam[t.team][k] != null));

      let boxHtml = "";
      const boxTeams = [winner, loser].filter((t) => t && boxByTeam[t.team]);
      if (boxTeams.length) {
        const head = ["Q1", "Q2", "Q3", "Q4", ...activeOT, "TOT"]
          .map((h) => `<th>${h}</th>`).join("");
        const body = boxTeams.map((t) => {
          const b = boxByTeam[t.team];
          const q = ["Q1", "Q2", "Q3", "Q4"].map((k) => Number(b[k] || 0));
          const ot = activeOT.map((k) => Number(b[k] || 0));
          const tot = [...q, ...ot].reduce((a, v) => a + v, 0);
          const cells = [...q, ...ot, tot].map((v) => `<td>${v}</td>`).join("");
          return `<tr>${cells}</tr>`;
        }).join("");
        boxHtml = `<div class="mini-boxscore table-responsive"><table class="table table-sm">
          <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
      }

      cards.push(`<article class="game-card">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="game-status">${esc(winner.state || "Final")}</span>
        </div>
        ${teamRow(winner, false)}
        ${teamRow(loser, true)}
        ${boxHtml}
      </article>`);
    }
    gameList.innerHTML = cards.join("");
  }

  // ---- Totals table (search by player) ----
  const totals = data.totals || [];
  const head = document.getElementById("totals-head");
  const body = document.getElementById("totals-body");
  if (totals.length) {
    const cols = Object.keys(totals[0]);
    head.innerHTML = cols.map((c) => `<th>${esc(c)}</th>`).join("");
    body.innerHTML = totals.map((row) =>
      `<tr>${cols.map((c) => `<td>${esc(fmt(row[c]))}</td>`).join("")}</tr>`).join("");
    document.getElementById("totalRows").textContent = totals.length;
    document.getElementById("visibleRows").textContent = totals.length;

    const searchBox = document.getElementById("searchBox");
    const rows = Array.from(body.getElementsByTagName("tr"));
    const playerCol = cols.indexOf("Player");
    searchBox.addEventListener("input", () => {
      const q = searchBox.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach((r) => {
        const name = (r.cells[playerCol]?.textContent || "").toLowerCase();
        const show = name.includes(q);
        r.style.display = show ? "" : "none";
        if (show) visible++;
      });
      document.getElementById("visibleRows").textContent = visible;
    });
  } else {
    body.innerHTML = `<tr><td>No player totals available.</td></tr>`;
  }

  function fmt(v) {
    if (v === null || v === undefined || v === "") return "-";
    if (typeof v === "number" && Number.isInteger(v)) return v;
    return v;
  }
})();
