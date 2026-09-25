// Fills the results page from data/*.json (written by eval/metrics.py --export).
// Two sections share these renderers: the sized eval (results.json) and the frozen pilot.
import { onThemePalette } from "./chart-theme.js";

const QUESTIONS = {
  scope_creep: "Scope creep",
  single_use_abstraction: "Unused abstraction",
  duplication: "Duplication",
  weakened_tests: "Weakened tests",
};
// The pilot asked the abstraction question in its old wording; label it as such (short, so it fits on phones).
const PILOT_QUESTIONS = { ...QUESTIONS, single_use_abstraction: "Used once (old)" };
// Emphasis, not categorical: Jev in the brand primary, Claude as grey context.
// Identity never rests on colour alone: each runner has its own marker shape, a legend and the table.
// Filled shapes only: Chart.js draws star/cross as outlines, which the surface-coloured ring would hide.
const SHAPES = [
  { pointStyle: "circle" },
  { pointStyle: "triangle" },
  { pointStyle: "rect" },
  { pointStyle: "rectRot" },
  { pointStyle: "triangle", rotation: 180 },
];
// Each runner sits slightly above or below the row line, so equal scores stay visible.
const NUDGE = 0.13;
const isJev = (name) => name.startsWith("Jev");

const fmt = (v, digits = 2) => (v === null || v === undefined ? "—" : v.toFixed(digits));
const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
const secs = (ms) => (ms === null || ms === undefined ? "—" : `${(ms / 1000).toFixed(1)} s`);
// Jev costs fractions of a cent, so show enough significant digits to be non-zero.
const usd = (v) => (v === null || v === undefined ? "not logged" : `$${v.toPrecision(2)}`);

// "#686040" -> "rgba(104, 96, 64, a)": a lighter grey over the surface without a new colour token.
function withAlpha(hex, alpha) {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function fill(section, data) {
  for (const el of section.querySelectorAll("[data-fill]")) {
    const key = el.dataset.fill;
    if (key === "fixtures") el.textContent = data.fixtures_total;
    if (key === "generated") el.textContent = data.generated;
    if (key === "scored") el.textContent = data.fixtures_scored;
  }
}

function kpis(section, data) {
  const jev = data.runners.find((r) => r.name === "Jev, without BAML");
  const target = section.querySelector(".kpis");
  if (!jev || !target) return;
  const s = jev.summary;
  const aucs = Object.values(s.concerns).map((c) => c.auc_pre);
  const items = [
    ["AUC, first answer", `${fmt(Math.min(...aucs))}–${fmt(Math.max(...aucs))}`],
    ["Good changes wrongly blocked", pct(s.pre.false_reject_rate)],
    ["Per-request time, p95", secs(s.latency_ms?.p95)],
    ["Blocked by firewall", `${s.errors.fixtures.length} of ${data.fixtures_total}`],
  ];
  target.replaceChildren(
    ...items.map(([label, value]) => {
      const div = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = value;
      div.append(dt, dd);
      return div;
    }),
  );
}

function header(row, text, { cols = 1, rows = 1, scope = "col" } = {}) {
  const cell = document.createElement("th");
  cell.textContent = text;
  cell.colSpan = cols;
  cell.rowSpan = rows;
  cell.scope = scope;
  row.append(cell);
}

function table(section, data, questions) {
  const qs = Object.keys(questions);
  // Two header rows: grouped columns keep the table narrow enough to read without scrolling on desktop.
  const thead = document.createElement("thead");
  const top = thead.insertRow();
  const sub = thead.insertRow();
  header(top, "Runner", { rows: 2 });
  header(top, "AUC, first answer", { cols: qs.length, scope: "colgroup" });
  header(top, "Fast first check", { cols: 2, scope: "colgroup" });
  header(top, "Per-request p50 / p95", { rows: 2 });
  header(top, "Cost per check", { rows: 2 });
  header(top, "Bars passed", { rows: 2 });
  for (const q of Object.values(questions)) header(sub, q);
  header(sub, "Wrongly blocked");
  header(sub, "Caught");
  const tbody = document.createElement("tbody");
  for (const r of data.runners) {
    const s = r.summary;
    const row = tbody.insertRow();
    if (isJev(r.name)) row.className = "jev";
    header(row, r.name, { scope: "row" });
    const lat = s.latency_ms ? `${secs(s.latency_ms.p50)} / ${secs(s.latency_ms.p95)}` : "not logged";
    const checks = Object.values(r.checks);
    const cells = [
      ...qs.map((q) => fmt(s.concerns[q].auc_pre)),
      pct(s.pre.false_reject_rate),
      pct(s.pre.catch_rate),
      lat,
      usd(s.cost_usd?.per_call),
      `${checks.filter(Boolean).length} of ${checks.length}`,
    ];
    for (const c of cells) row.insertCell().textContent = c;
  }
  section.querySelector("table.results").append(thead, tbody);
}

// Threshold trade-off of the fast first check, one row per threshold, one column pair per runner.
function sweepTable(section, data) {
  const target = section.querySelector("table.sweep");
  if (!target) return;
  const runners = data.runners.filter((r) => r.sweep);
  const thead = document.createElement("thead");
  const top = thead.insertRow();
  const sub = thead.insertRow();
  header(top, "Reject at", { rows: 2 });
  for (const r of runners) header(top, r.name, { cols: 2, scope: "colgroup" });
  for (const _ of runners) {
    header(sub, "Wrongly blocked");
    header(sub, "Caught");
  }
  const tbody = document.createElement("tbody");
  runners[0].sweep.forEach((first, i) => {
    const row = tbody.insertRow();
    header(row, first.threshold.toFixed(2), { scope: "row" });
    for (const r of runners) {
      row.insertCell().textContent = pct(r.sweep[i].false_reject_rate);
      row.insertCell().textContent = pct(r.sweep[i].catch_rate);
    }
  });
  target.append(thead, tbody);
}

function chart(section, data, questions) {
  const labels = Object.values(questions);
  const qs = Object.keys(questions);
  const aucs = data.runners.flatMap((r) => qs.map((q) => r.summary.concerns[q].auc_pre)).filter((v) => v !== null);
  // Start the axis at the 0.05 step below the lowest score, never above 0.85; the note says where it starts.
  const min = Math.min(0.85, Math.floor(Math.min(...aucs) * 20) / 20);
  const axisNote = section.querySelector("[data-fill=axis-min]");
  if (axisNote) axisNote.textContent = min.toFixed(2);
  const c = new Chart(section.querySelector("canvas"), {
    type: "scatter",
    data: {
      datasets: data.runners.map((r, i) => ({
        label: r.name,
        data: qs.map((q, y) => ({ x: r.summary.concerns[q].auc_pre, y: y + (i - (data.runners.length - 1) / 2) * NUDGE })),
        ...SHAPES[i % SHAPES.length],
        clip: false, // a score of 1.00 sits on the right edge
        pointRadius: 7,
        pointHoverRadius: 9,
        pointHitRadius: 10,
        borderWidth: 2,
      })),
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: { min, max: 1.0, ticks: { stepSize: 0.05 }, title: { display: true, text: "AUC (first answer)" } },
        y: {
          type: "linear",
          reverse: true,
          min: -0.5,
          max: labels.length - 0.5,
          afterBuildTicks: (axis) => {
            axis.ticks = labels.map((_, v) => ({ value: v }));
          },
          ticks: { callback: (v) => labels[v] ?? "" },
          grid: { display: false },
        },
      },
      plugins: {
        legend: { position: "top", labels: { usePointStyle: true } },
        tooltip: {
          callbacks: {
            title: (items) => labels[Math.round(items[0].parsed.y)],
            label: (item) => `${item.dataset.label}: AUC ${fmt(item.parsed.x)}`,
          },
        },
      },
    },
  });

  onThemePalette((p) => {
    const context = withAlpha(p.textMuted, 0.55);
    for (const ds of c.data.datasets) {
      ds.backgroundColor = isJev(ds.label) ? p.primary : context;
      ds.borderColor = p.surface; // 2px surface ring keeps overlapping markers apart
    }
    for (const axis of Object.values(c.options.scales)) {
      axis.ticks.color = p.textMuted;
      if (axis.title) axis.title.color = p.textMuted;
      if (axis.grid.display !== false) axis.grid.color = p.border;
      axis.border = { color: p.border };
    }
    c.options.plugins.legend.labels.color = p.text;
    c.update();
  });
}

async function render(id, url, questions) {
  const section = document.getElementById(id);
  const data = await (await fetch(url)).json();
  fill(section, data);
  kpis(section, data);
  chart(section, data, questions);
  table(section, data, questions);
  sweepTable(section, data);
}

await render("sized", "data/results.json", QUESTIONS);
await render("pilot", "data/pilot-2026-09-24.json", PILOT_QUESTIONS);
