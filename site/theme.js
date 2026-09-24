// theme.js — qte77 shared theme cycler (no-build ES module).
//
// Works with plain `<script type="module">` — no bundler (agentic-kit constraint).
// Pure logic (resolveTheme / nextTheme / isThemeMode / THEME_CYCLE) is DOM-free and
// unit-testable; DOM glue is in initThemeToggle(). Reference impl: analyze-stock-kpi.
//
// Pair with: ui-kit/anti-fouc.html (inline <head> guard), ui-kit/theme-toggle.html
// (markup), ui-kit/a11y.css (.sr-only + width-sizer), ui-kit/eyerest.css (tokens).

export const THEME_CYCLE = ["system", "light", "dark"];
export const STORAGE_KEY = "qte77-theme"; // standardized (decision D4)

// glyph + label per mode (decision D2: ◐ ○ ●)
export const THEME_META = {
  system: { glyph: "◐", label: "System" },
  light: { glyph: "○", label: "Light" },
  dark: { glyph: "●", label: "Dark" },
};

// widest label — used by a11y.css width-sizer; kept here as the single source.
export const WIDEST_LABEL = "System";

/** @returns {boolean} whether `v` is one of system|light|dark */
export function isThemeMode(v) {
  return THEME_CYCLE.includes(v);
}

/**
 * Resolve the active mode by precedence: ?theme= › localStorage › "system".
 * Pure — pass the two raw strings in; no DOM/storage access here.
 */
export function resolveTheme(urlValue, lsValue) {
  if (isThemeMode(urlValue)) return urlValue;
  if (isThemeMode(lsValue)) return lsValue;
  return "system";
}

/** Next mode in the cycle (wraps). */
export function nextTheme(mode) {
  const i = THEME_CYCLE.indexOf(mode);
  return THEME_CYCLE[(i + 1) % THEME_CYCLE.length];
}

/** Effective light|dark for a mode (resolves "system" against the OS preference). */
export function effectiveTheme(mode) {
  if (mode === "light" || mode === "dark") return mode;
  const dark =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return dark ? "dark" : "light";
}

/**
 * Apply a mode to the document: set/remove html[data-theme], persist, update the
 * toggle's accessible name + label, announce via the live region, and emit
 * `themechange` (so charts/canvases recolour). Returns the applied mode.
 */
export function applyTheme(mode, { persist = true } = {}) {
  const root = document.documentElement;
  if (mode === "light" || mode === "dark") {
    root.setAttribute("data-theme", mode); // explicit scheme
  } else {
    root.removeAttribute("data-theme"); // system → prefers-color-scheme governs
  }
  if (persist) {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch (_) {
      /* private mode / storage disabled — non-fatal */
    }
  }

  const meta = THEME_META[mode];
  const name = `Color theme: ${meta.label} (click to change)`;

  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.setAttribute("aria-label", name);
    btn.setAttribute("title", name);
    const g = btn.querySelector(".theme-glyph");
    const l = btn.querySelector(".theme-label");
    if (g) g.textContent = meta.glyph;
    if (l) l.textContent = meta.label;
  }

  const status = document.getElementById("theme-status");
  if (status) status.textContent = `Theme: ${meta.label}`;

  const effective = effectiveTheme(mode);
  document.dispatchEvent(
    new CustomEvent("themechange", { detail: { mode, effective } }),
  );
  return mode;
}

/**
 * Wire up the #theme-toggle button and initial state.
 * Reads ?theme= and localStorage, applies, and:
 *  - cycles on click;
 *  - in System mode, re-applies when the OS preference flips (keeps charts in sync);
 *  - supports keyboard Escape to blur (panel-close hook left to the app).
 */
export function initThemeToggle() {
  const url = new URLSearchParams(location.search).get("theme");
  let ls = null;
  try {
    ls = localStorage.getItem(STORAGE_KEY);
  } catch (_) {
    /* ignore */
  }
  let mode = resolveTheme(url, ls);
  // don't persist a URL-driven choice over the stored one unless it's already stored
  applyTheme(mode, { persist: isThemeMode(ls) || isThemeMode(url) });

  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.addEventListener("click", () => {
      mode = nextTheme(mode);
      applyTheme(mode);
    });
  }

  if (window.matchMedia) {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", () => {
        if (mode === "system") applyTheme("system"); // re-emit themechange
      });
  }
}

// Auto-init when imported directly by a page (no-build friendly). Apps that want to
// control timing can import the functions and skip this by loading as a module that
// only re-exports.
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initThemeToggle, { once: true });
  } else {
    initThemeToggle();
  }
}
