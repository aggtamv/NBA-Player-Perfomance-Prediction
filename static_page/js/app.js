// Shared layout: injects the top navigation and wires the dark-mode toggle.
// Static replacement for base.html (no Flask, no server-side rendering).
(function () {
  const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  const tabs = [
    { href: "index.html", label: "Home", match: ["", "index.html"] },
    { href: "stats.html", label: "Stats", match: ["stats.html"] },
    { href: "prediction.html", label: "Predictions", match: ["prediction.html"] },
  ];

  const navItems = tabs
    .map((t) => {
      const active = t.match.includes(page) ? "active-tab" : "";
      return `<li class="nav-item"><a class="nav-link tab-pill ${active}" href="${t.href}">${t.label}</a></li>`;
    })
    .join("");

  const headerHtml = `
    <header class="app-header">
      <nav class="navbar navbar-expand-md" id="navbar-main" aria-label="Main navigation">
        <div class="container-fluid px-3 px-lg-4">
          <a class="navbar-brand app-brand" href="index.html">
            <img src="img/logo.png" class="app-brand-logo" alt="NBA Oracle">
            <span>NBA Profit</span>
          </a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav" aria-controls="mainNav" aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div class="collapse navbar-collapse" id="mainNav">
            <ul class="navbar-nav app-nav mx-md-auto mt-3 mt-md-0">${navItems}</ul>
            <div class="app-user-menu mt-3 mt-md-0">
              <button class="theme-toggle" type="button" id="themeToggle" aria-label="Toggle dark mode">
                <span class="theme-toggle-track" aria-hidden="true">
                  <span class="theme-toggle-icon theme-toggle-sun"></span>
                  <span class="theme-toggle-icon theme-toggle-moon"></span>
                  <span class="theme-toggle-thumb"></span>
                </span>
              </button>
            </div>
          </div>
        </div>
      </nav>
    </header>`;

  const mount = document.getElementById("app-header");
  if (mount) mount.outerHTML = headerHtml;

  // Dark-mode toggle (theme is pre-set inline in each page's <head> to avoid flash)
  const themeToggle = document.getElementById("themeToggle");
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.bsTheme = theme;
    localStorage.setItem("nba-oracle-theme", theme);
    window.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next);
    });
  }
})();

// Small helper shared across pages
window.NBA = {
  async loadJSON(path) {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(`Failed to load ${path} (${res.status})`);
    return res.json();
  },
};
