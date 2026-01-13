(() => {
  const THEME_KEY = "mystrix_theme";
  const themes = ["core", "experiment"];

  function applyTheme(theme) {
    if (!themes.includes(theme)) theme = "core";
    document.documentElement.dataset.theme = theme;
    document.body.classList.remove("theme-core", "theme-experiment");
    document.body.classList.add(`theme-${theme}`);
    try { localStorage.setItem(THEME_KEY, theme); } catch (_) {}
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.textContent = `Theme: ${theme === "core" ? "Glass Neon" : "Experiment"}`;
    });
  }

  function currentTheme() {
    try {
      const t = localStorage.getItem(THEME_KEY);
      if (themes.includes(t)) return t;
    } catch (_) {}
    return "core";
  }

  function toggleTheme() {
    const next = currentTheme() === "core" ? "experiment" : "core";
    applyTheme(next);
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(currentTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      if (!btn.dataset.bound) {
        btn.dataset.bound = "1";
        btn.addEventListener("click", toggleTheme);
      }
    });
  });

  window.MystrixTheme = { applyTheme, currentTheme, toggleTheme };
})();
