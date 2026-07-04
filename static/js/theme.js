// Light/Dark theme toggle. Persists the choice in localStorage under
// "pdu-theme" and reflects it as html[data-theme="..."]. Default is light
// (no attribute = :root light palette). The no-flash pre-paint script lives
// inline in <head> (see base.html) so the correct theme is applied before
// first paint; this file only wires up the toggle buttons and keeps the
// segmented control's active state in sync.
(function () {
  "use strict";

  const STORAGE_KEY = "pdu-theme";
  const root = document.documentElement;

  function currentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function syncButtons(theme) {
    document.querySelectorAll(".theme-seg").forEach((btn) => {
      const isActive = btn.dataset.theme === theme;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function setTheme(theme) {
    theme = theme === "dark" ? "dark" : "light";
    if (theme === "dark") {
      root.setAttribute("data-theme", "dark");
    } else {
      // Remove the attribute so :root (light) applies — keeps light as default.
      root.removeAttribute("data-theme");
    }
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}
    syncButtons(theme);
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".theme-seg");
    if (!btn) return;
    setTheme(btn.dataset.theme);
  });

  syncButtons(currentTheme());
})();
