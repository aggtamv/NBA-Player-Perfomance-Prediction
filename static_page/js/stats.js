// Stats page: renders metric cards, two Plotly line charts (with metric toggles),
// a recent-form bar chart + chip strip, and the season tables — all from stats.json.
(async function () {
  let S;
  try {
    S = await NBA.loadJSON("data/stats.json");
  } catch (e) {
    document.getElementById("rawShootingChart").innerHTML =
      `<div class="alert alert-danger status-empty">Could not load stats data.</div>`;
    return;
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const rawShootingRows = S.shooting_chart || [];
  const adjustedShootingRows = S.adjusted_chart || [];
  const recentFormRows = S.recent_form_chart || [];
  const staticImgBase = "img/";
  const chartColors = ['#17408b', '#c9082a', '#d9911b', '#15803d', '#6d28d9', '#0f766e', '#0f766e', '#7c2d12', '#334155'];
  const plotConfig = { responsive: true, displayModeBar: false };

  // ---- Metric cards ----
  const m = S.metrics || {};
  const x = S.metrics_extra || {};
  const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setText("year-range", m.year_range || "No data");
  setText("m-gold-players", x.gold_players ?? "-");
  setText("m-gold-top", x.gold_top_player || "-");
  setText("m-gold-top-note", x.gold_top_points != null ? `${x.gold_top_points.toFixed(1)} PPG over prior 10` : "Gold table unavailable");
  setText("m-efg", m.latest_efg != null ? `${m.latest_efg.toFixed(1)}%` : "-");
  setText("m-efg-note", m.latest_efg_delta != null ? `${m.latest_efg_delta >= 0 ? "+" : ""}${m.latest_efg_delta.toFixed(1)} pts vs prior year` : "No prior-year delta");
  setText("m-3par", m.three_point_rate_change != null ? `${m.three_point_rate_change >= 0 ? "+" : ""}${m.three_point_rate_change.toFixed(1)} pts` : "-");
  setText("rf-count", `${x.gold_players || 0} players shown`);

  // ---- Metric toggle chips ----
  function buildToggles(containerId, options, defaults, chartName) {
    const c = document.getElementById(containerId);
    c.innerHTML = options.map((metric) =>
      `<label class="metric-toggle"><input type="checkbox" value="${esc(metric)}" data-chart="${chartName}" ${defaults.includes(metric) ? "checked" : ""}><span>${esc(metric)}</span></label>`
    ).join("");
  }
  buildToggles("raw-metrics", S.raw_metric_options || [], S.raw_default_metrics || [], "raw");
  buildToggles("adjusted-metrics", S.adjusted_metric_options || [], S.adjusted_default_metrics || [], "adjusted");

  function chartTheme() {
    const isDark = document.documentElement.dataset.theme === 'dark';
    return {
      text: isDark ? '#e5e7eb' : '#111827',
      plot: isDark ? 'rgba(15,23,42,0.72)' : 'rgba(255,255,255,0.84)',
      grid: isDark ? 'rgba(148,163,184,0.22)' : 'rgba(207, 218, 232, 0.7)',
      axis: isDark ? '#9ca3af' : '#17408b'
    };
  }

  function selectedMetrics(chartName) {
    return Array.from(document.querySelectorAll(`input[data-chart="${chartName}"]:checked`)).map((i) => i.value);
  }

  function renderMetricChart(elementId, rows, metrics, title) {
    const theme = chartTheme();
    const data = metrics.map((metric, index) => ({
      x: rows.map((r) => r.Year),
      y: rows.map((r) => r[metric]),
      name: metric,
      mode: 'lines+markers',
      line: { width: 3, color: chartColors[index % chartColors.length] },
      marker: { size: 6 },
      hovertemplate: `%{x}<br>${metric}: %{y:.1%}<extra></extra>`
    }));
    const layout = {
      title: { text: title, x: 0, xanchor: 'left', font: { size: 15 } },
      height: 420, margin: { l: 48, r: 24, t: 52, b: 44 },
      legend: { orientation: 'h', y: -0.18 },
      font: { family: 'Inter, Segoe UI, Arial', color: theme.text },
      paper_bgcolor: 'rgba(255,255,255,0)', plot_bgcolor: theme.plot, hovermode: 'x unified',
      xaxis: { showgrid: false, fixedrange: true },
      yaxis: { tickformat: '.0%', gridcolor: theme.grid, fixedrange: true }
    };
    Plotly.react(elementId, data, layout, plotConfig);
  }

  function updateCharts() {
    renderMetricChart('rawShootingChart', rawShootingRows, selectedMetrics('raw'), 'Shot Profile and Finishing');
    renderMetricChart('adjustedShootingChart', adjustedShootingRows, selectedMetrics('adjusted'), 'Efficiency and Shot Mix');
  }

  function renderRecentFormChart() {
    const theme = chartTheme();
    const players = recentFormRows.map((r) => r.player);
    const ranks = recentFormRows.map((_, i) => `#${i + 1}`);
    const series = [
      { key: 'last_10_points_avg', name: 'Points', color: '#17408b' },
      { key: 'last_10_assists_avg', name: 'Assists', color: '#c9082a' },
      { key: 'last_10_reboundsTotal_avg', name: 'Rebounds', color: '#d9911b' },
    ];
    const data = series.map((s) => ({
      x: ranks, y: recentFormRows.map((r) => r[s.key]), customdata: players,
      name: s.name, type: 'bar', marker: { color: s.color },
      hovertemplate: `%{customdata}<br>${s.name}: %{y:.1f}<extra></extra>`
    }));
    const layout = {
      title: { text: 'Top Recent Form Leaders', x: 0, xanchor: 'left', font: { size: 15 } },
      barmode: 'group', height: 430, margin: { l: 52, r: 24, t: 52, b: 58 },
      legend: { orientation: 'h', y: -0.16 },
      font: { family: 'Inter, Segoe UI, Arial', color: theme.text },
      paper_bgcolor: 'rgba(255,255,255,0)', plot_bgcolor: theme.plot, hovermode: 'closest',
      xaxis: { fixedrange: true, tickfont: { size: 12, color: theme.axis } },
      yaxis: { title: 'Prior 10 game average', gridcolor: theme.grid, fixedrange: true }
    };
    Plotly.react('recentFormChart', data, layout, plotConfig);
    renderRecentFormPlayers();
  }

  function initialsForName(name) {
    return name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
  }

  function renderRecentFormPlayers() {
    const container = document.getElementById('recentFormPlayers');
    if (!container) return;
    container.innerHTML = '';
    recentFormRows.forEach((row, index) => {
      const chip = document.createElement('div');
      chip.className = 'player-chip';
      chip.innerHTML = `
        <img class="player-chip-bg-logo" src="${staticImgBase}${esc(row.team_logo || 'nba.svg')}" alt="" aria-hidden="true">
        <span class="player-chip-rank">#${index + 1}</span>
        <span class="player-chip-avatar">${esc(initialsForName(row.player))}</span>
        <span class="player-chip-identity">
          <span class="player-chip-name">${esc(row.player)}</span>
          <span class="player-chip-team">${esc(row.team || 'NBA')}</span>
        </span>
        <span class="player-chip-stat">${Number(row.last_10_points_avg).toFixed(1)} PPG</span>`;
      container.appendChild(chip);
    });
  }

  // ---- Tables ----
  function fillTable(headId, bodyId, columns, rows) {
    document.getElementById(headId).innerHTML = columns.map((c) =>
      `<th>${esc(c === 'opponent' ? 'Last Opponent' : c)}</th>`).join("");
    const body = document.getElementById(bodyId);
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${columns.length || 1}">No data available.</td></tr>`;
      return;
    }
    body.innerHTML = rows.map((row) =>
      `<tr>${columns.map((c) => `<td>${esc(row[c])}</td>`).join("")}</tr>`).join("");
  }
  fillTable("rf-head", "rf-body", S.recent_form_columns || [], S.recent_form_table || []);
  fillTable("raw-tbl-head", "raw-tbl-body", S.shooting_columns || [], S.shooting_table || []);
  fillTable("adj-tbl-head", "adj-tbl-body", S.adjusted_columns || [], S.adjusted_table || []);

  document.querySelectorAll('.metric-toggle input').forEach((i) => i.addEventListener('change', updateCharts));
  updateCharts();
  renderRecentFormChart();
  window.addEventListener('themechange', () => { updateCharts(); renderRecentFormChart(); });
})();
