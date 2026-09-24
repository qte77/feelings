// chart-theme.js — bind a Chart.js (or any canvas) config to the live EyeRest tokens.
//
// Reads the *resolved* CSS custom properties, so it's automatically correct for whatever
// html[data-variant] / [data-theme] is active — no per-variant JS palette to drift from
// DESIGN.md. Recolours on theme.js's `themechange` event. The categorical colours come from the
// brand's zero-blue `--data-*` arc (positive/caution/negative/alt) — never hardcode chart hex.
//
// No build. Load after eyerest.css (so the tokens resolve) and theme.js (so the event fires):
//   import { onThemePalette } from "./chart-theme.js";
//   onThemePalette((p) => { chart.data.datasets[0].backgroundColor = p.arc; chart.update(); });

const NAMED = {
  primary: "--primary",
  text: "--text",
  textMuted: "--text-muted",
  border: "--border",
  surface: "--surface",
};

// Categorical arc, in cascade order — matches DESIGN.md `data` (zero-blue).
const ARC = ["--data-positive", "--data-caution", "--data-negative", "--data-alt"];

function readVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** The current resolved palette: named tokens + the categorical `data` arc (array). */
export function getChartPalette() {
  const named = Object.fromEntries(Object.entries(NAMED).map(([k, v]) => [k, readVar(v)]));
  return { ...named, arc: ARC.map(readVar) };
}

/**
 * Call `paint(getChartPalette())` now and on every theme/variant change; returns an unsubscribe fn.
 * `paint` typically recolours the chart's datasets/scales then calls `chart.update()`.
 */
export function onThemePalette(paint) {
  const run = () => paint(getChartPalette());
  run();
  document.addEventListener("themechange", run);
  return () => document.removeEventListener("themechange", run);
}
