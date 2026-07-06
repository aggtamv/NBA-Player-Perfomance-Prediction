// Prediction page: calls the Hugging Face Space (aggtamv/nba_plusminus) DIRECTLY
// from the browser via the Gradio JS client. No Flask backend involved.
//
// Two input flows, both hitting the model's /predict_from_csv endpoint:
//   1. Player tab  -> look up the player's precomputed last-10x20 matrix
//                     (data/players_predict.json), build a CSV in-memory, send it.
//   2. CSV Upload  -> send the user's uploaded file straight to the model.
import { Client } from "https://esm.sh/@gradio/client@1.10.0";

const SPACE = "aggtamv/nba_plusminus";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const resultArea = document.getElementById("result-area");
const predictBtn = document.getElementById("predict-btn");

let clientPromise = null;         // lazy, reused across predictions
let predictData = { columns: [], players: {} };

// --- Load precomputed player matrices + name list -------------------------
(async function loadPlayers() {
  try {
    predictData = await NBA.loadJSON("data/players_predict.json");
  } catch (e) {
    console.error("Could not load player matrices", e);
  }
})();

// --- Autocomplete ---------------------------------------------------------
const playerInput = document.getElementById("player_name");
const suggestions = document.getElementById("playerSuggestions");
let activeIndex = -1;

function clearSuggestions() {
  suggestions.innerHTML = "";
  suggestions.classList.remove("is-open");
  activeIndex = -1;
}

function searchNames(query) {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  return Object.keys(predictData.players || {})
    .filter((name) => name.toLowerCase().includes(q))
    .sort()
    .slice(0, 12);
}

function renderSuggestions(names) {
  suggestions.innerHTML = "";
  if (!names.length) { clearSuggestions(); return; }
  names.forEach((name, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "autocomplete-option";
    btn.role = "option";
    btn.textContent = name;
    btn.dataset.index = index;
    btn.addEventListener("click", () => { playerInput.value = name; clearSuggestions(); });
    suggestions.appendChild(btn);
  });
  suggestions.classList.add("is-open");
}

function setActiveOption(next) {
  const options = Array.from(suggestions.querySelectorAll(".autocomplete-option"));
  if (!options.length) return;
  activeIndex = (next + options.length) % options.length;
  options.forEach((o, i) => o.classList.toggle("is-active", i === activeIndex));
}

playerInput.addEventListener("input", () => {
  const q = playerInput.value.trim();
  if (q.length < 2) { clearSuggestions(); return; }
  renderSuggestions(searchNames(q));
});
playerInput.addEventListener("keydown", (e) => {
  const options = Array.from(suggestions.querySelectorAll(".autocomplete-option"));
  if (e.key === "ArrowDown") { e.preventDefault(); setActiveOption(activeIndex + 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); setActiveOption(activeIndex - 1); }
  else if (e.key === "Enter" && activeIndex >= 0 && options[activeIndex]) {
    e.preventDefault(); playerInput.value = options[activeIndex].textContent; clearSuggestions();
  } else if (e.key === "Escape") { clearSuggestions(); }
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete")) clearSuggestions();
});

// --- Helpers --------------------------------------------------------------
function matrixToCsvFile(columns, matrix, name) {
  const header = columns.join(",");
  const body = matrix.map((row) => row.join(",")).join("\n");
  const csv = `${header}\n${body}\n`;
  return new File([csv], `${name}.csv`, { type: "text/csv" });
}

function renderPlayerStats(columns, matrix, name) {
  const panel = document.getElementById("player-stats-panel");
  document.getElementById("player-stats-name").textContent = name;
  document.getElementById("ps-head").innerHTML = columns.map((c) => `<th>${esc(c)}</th>`).join("");
  document.getElementById("ps-body").innerHTML = matrix.map((row) =>
    `<tr>${row.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("");
  panel.style.display = "";
}

function setResult(html, cls = "prediction-result") {
  resultArea.innerHTML = `<div class="alert ${cls} mb-0">${html}</div>`;
}

function setBusy(busy, label) {
  predictBtn.disabled = busy;
  predictBtn.textContent = busy ? (label || "Predicting…") : "Predict";
}

async function getClient() {
  if (!clientPromise) clientPromise = Client.connect(SPACE);
  return clientPromise;
}

async function predictFromFile(file) {
  const app = await getClient();
  const out = await app.predict("/predict_from_csv", { file });
  // Textbox return -> out.data[0]
  return Array.isArray(out.data) ? out.data[0] : out.data;
}

// --- Submit ---------------------------------------------------------------
document.getElementById("predict-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const uploadTabActive = document.getElementById("upload-tab").classList.contains("active");
  document.getElementById("player-stats-panel").style.display = "none";

  try {
    setBusy(true, "Connecting…");
    setResult('<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm" aria-hidden="true"></div><div>Contacting the model… (a sleeping Space can take ~30s to wake)</div></div>', "alert-info");

    let file, name, matrix;

    if (uploadTabActive) {
      const input = document.getElementById("csv_file");
      if (!input.files.length) { setResult("Please choose a CSV file to upload.", "alert-warning"); setBusy(false); return; }
      file = input.files[0];
      name = file.name;
    } else {
      name = playerInput.value.trim();
      if (!name) { setResult("Please select a player.", "alert-warning"); setBusy(false); return; }
      matrix = (predictData.players || {})[name];
      if (!matrix) { setResult(`No recent 10-game data available for “${esc(name)}”. Pick a suggested player.`, "alert-warning"); setBusy(false); return; }
      file = matrixToCsvFile(predictData.columns, matrix, name);
    }

    setBusy(true, "Predicting…");
    const prediction = await predictFromFile(file);
    setResult(esc(prediction));

    if (matrix) renderPlayerStats(predictData.columns, matrix, name);
  } catch (err) {
    console.error(err);
    setResult(`Prediction failed: ${esc(err.message || err)}`, "alert-danger");
  } finally {
    setBusy(false);
  }
});
