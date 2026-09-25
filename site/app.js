// Fills the results page from data/*.json (written by eval/metrics.py --export).
// Layers: 0 answer + tiles, 1 per-question ratings, then <details> for compare / strictness / method.
// Rating thresholds and ratio rules are recorded in the plan's "Decisions and defaults".
import { onThemePalette } from "./chart-theme.js";

const QUESTIONS = {
  scope_creep: "Scope creep",
  single_use_abstraction: "Unused abstraction",
  duplication: "Duplicated code",
  weakened_tests: "Weakened tests",
};
// The earlier test asked the abstraction question in its old wording; label it as such (short, fits phones).
const PILOT_QUESTIONS = { ...QUESTIONS, single_use_abstraction: "Used once (old)" };
const HEADLINE = "Jev, without BAML"; // the two setups agree within 0.02, so one carries the headline
const CURRENT_THRESHOLD = 0.7;
const FRR_LIMIT = 0.05;
const RATINGS = [
  [0.95, "excellent", 5],
  [0.85, "good", 4],
  [0.8, "fair", 3],
  [0, "weak", 2],
];
// Emphasis, not categorical: Jev in the brand primary, Claude as grey context.
// Identity never rests on colour alone: each setup has its own marker shape, a legend and a table.
const SHAPES = [
  { pointStyle: "circle" },
  { pointStyle: "triangle" },
  { pointStyle: "rect" },
  { pointStyle: "rectRot" },
  { pointStyle: "triangle", rotation: 180 },
];
const NUDGE = 0.13; // each setup sits slightly off the row line, so equal scores stay visible
const isJev = (name) => name.startsWith("Jev");

const fmt = (v, digits = 2) => (v === null || v === undefined ? "—" : v.toFixed(digits));
const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
const secs = (ms) => (ms === null || ms === undefined ? "—" : `${(ms / 1000).toFixed(1)} s`);
const usd = (v) => (v === null || v === undefined ? "not logged" : `$${v.toPrecision(2)}`);
const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
// One significant figure, for "about N times" claims.
const roughly = (x) => {
  const p = 10 ** Math.floor(Math.log10(x));
  return Math.round(x / p) * p;
};
const rating = (auc) => RATINGS.find(([min]) => auc >= min);
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
};

function withAlpha(hex, alpha) {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function fill(key, value) {
  for (const node of document.querySelectorAll(`[data-fill="${key}"]`)) node.textContent = value;
}

// ---- Layer 0 ---------------------------------------------------------------------------------

function answer(sized) {
  const jev = sized.runners.find((r) => r.name === HEADLINE).summary;
  const pre = jev.pre;
  const flagged = Math.round(pre.false_reject_rate * pre.n_good);
  const caught = Math.round(pre.catch_rate * pre.n_bad);
  document.getElementById("verdict").textContent =
    `On ${sized.fixtures_total} labelled code changes, it caught ${pct(pre.catch_rate)} of problem changes and ` +
    `wrongly flagged ${flagged} of ${pre.n_good} good ones, in ${secs(jev.latency_ms.p95)} for ` +
    `${usd(jev.cost_usd.per_call)} per check.`;

  const claude = sized.runners.filter((r) => !isJev(r.name)).map((r) => r.summary);
  const p95s = claude.map((s) => s.latency_ms.p95);
  const costs = claude.map((s) => s.cost_usd.per_call);
  const tiles = [
    ["Catches", pct(pre.catch_rate), `of problem changes (${caught} of ${pre.n_bad})`],
    ["Wrongly flags", pct(pre.false_reject_rate), `of good changes (${flagged} of ${pre.n_good})`],
    [
      "Per check",
      `${secs(jev.latency_ms.p95)} · ${usd(jev.cost_usd.per_call)}`,
      `vs ${secs(Math.min(...p95s))}–${secs(Math.max(...p95s))} and ${usd(Math.min(...costs))}–${usd(Math.max(...costs))} for Claude`,
    ],
  ];
  document.getElementById("tiles").replaceChildren(
    ...tiles.map(([label, value, sub]) => {
      const div = el("div");
      div.append(el("dt", label), el("dd", value), el("dd", sub, "sub"));
      return div;
    }),
  );
}

// ---- Layer 1 ---------------------------------------------------------------------------------

// What a problem example of each kind looks like in the test set (see eval/fixtures.README.md).
const EXAMPLES = {
  scope_creep: "A change that also adds an unrelated helper, e.g. a slugify() function the message never mentions.",
  single_use_abstraction: "A new config class that is created once and whose result nothing else uses.",
  duplication: "A near-copy of a function added elsewhere in the same change, under a different name.",
  weakened_tests: "An assertion loosened, e.g. assert status == 200 becomes assert status, or a test skipped.",
};

function ratings(sized) {
  const jev = sized.runners.find((r) => r.name === HEADLINE).summary.concerns;
  const rows = Object.entries(QUESTIONS)
    .map(([key, label]) => ({ key, label, auc: jev[key].auc_pre }))
    .sort((a, b) => b.auc - a.auc);
  document.getElementById("ratings").replaceChildren(
    ...rows.map(({ key, label, auc }) => {
      const [, word, dots] = rating(auc);
      const li = el("li");
      const details = el("details", undefined, "rating");
      const summary = el("summary");
      const meter = el("span", "", `dots d${dots}`);
      meter.setAttribute("aria-hidden", "true");
      summary.append(el("span", label, "q"), meter, el("span", word, "word"), el("span", fmt(auc), "num"));
      const body = el("div", undefined, "rating-body");
      // The exact wording comes from eval/concerns.py via the export, the same text both runners send.
      body.append(el("p", `“${sized.questions[key]}”`, "asked"), el("p", `Problem example: ${EXAMPLES[key]}`, "note"));
      details.append(summary, body);
      li.append(details);
      return li;
    }),
  );
  // Largest per-question gap between the two setups.
  const [a, b] = sized.runners.map((r) => r.summary.concerns);
  const gap = Math.max(...Object.keys(QUESTIONS).map((k) => Math.abs(a[k].auc_pre - b[k].auc_pre)));
  document.getElementById("baml-note").textContent =
    gap <= 0.02
      ? "The same within 0.02 with or without BAML, so one set of numbers is shown."
      : `With and without BAML differ by up to ${fmt(gap)}; both are in the full results.`;
}

// ---- Layer 2 ---------------------------------------------------------------------------------

function compare(pilot) {
  const rows = pilot.runners.filter((r) => r.name !== "Jev, with BAML");
  const table = document.getElementById("compare-table");
  const head = table.createTHead().insertRow();
  for (const h of ["Setup", "Tells good from bad (average of 4)", "Wrongly flags", "Time", "Cost"]) {
    const th = el("th", h);
    th.scope = "col";
    head.append(th);
  }
  const body = table.createTBody();
  for (const r of rows) {
    const s = r.summary;
    const avg = mean(Object.keys(QUESTIONS).map((k) => s.concerns[k].auc_pre));
    const tr = body.insertRow();
    if (isJev(r.name)) tr.className = "jev";
    const th = el("th", r.name);
    th.scope = "row";
    tr.append(th);
    const barCell = tr.insertCell();
    const bar = el("span", "", "hbar");
    bar.style.setProperty("--w", `${avg * 100}%`);
    bar.setAttribute("aria-hidden", "true");
    barCell.append(bar, el("span", fmt(avg), "num"));
    tr.insertCell().textContent = pct(s.pre.false_reject_rate);
    tr.insertCell().textContent = secs(s.latency_ms?.p95);
    tr.insertCell().textContent = usd(s.cost_usd?.per_call);
  }
  const jev = rows.find((r) => isJev(r.name)).summary;
  const claude = rows.filter((r) => !isJev(r.name));
  const best = claude.reduce((x, y) =>
    mean(Object.keys(QUESTIONS).map((k) => x.summary.concerns[k].auc_pre)) >=
    mean(Object.keys(QUESTIONS).map((k) => y.summary.concerns[k].auc_pre))
      ? x
      : y,
  );
  const fastest = Math.min(...claude.map((r) => r.summary.latency_ms.p95));
  const cheapest = claude.reduce((x, y) => (x.summary.cost_usd.per_call <= y.summary.cost_usd.per_call ? x : y));
  document.getElementById("compare-summary").textContent =
    `In short: ${best.name} tells good from bad best. Jev is about ${roughly(fastest / jev.latency_ms.p95)}× faster ` +
    `than the fastest Claude and about ${roughly(cheapest.summary.cost_usd.per_call / jev.cost_usd.per_call)}× cheaper ` +
    `than the cheapest (${cheapest.name}).`;
}

// ---- Layer 3 ---------------------------------------------------------------------------------

function strictness(sized) {
  const jev = sized.runners.find((r) => r.name === HEADLINE);
  const { n_good, n_bad } = jev.summary.pre;
  const input = document.getElementById("threshold");
  const show = () => {
    const t = Number(input.value);
    const row = jev.sweep.reduce((x, y) => (Math.abs(y.threshold - t) < Math.abs(x.threshold - t) ? y : x));
    document.getElementById("threshold-out").textContent = row.threshold.toFixed(2);
    document.getElementById("threshold-current").textContent =
      Math.abs(row.threshold - CURRENT_THRESHOLD) < 1e-9 ? "(current setting)" : "";
    document.getElementById("catch-bar").style.width = `${row.catch_rate * 100}%`;
    document.getElementById("catch-value").textContent =
      `${pct(row.catch_rate)} of problem changes (${Math.round(row.catch_rate * n_bad)} of ${n_bad})`;
    // The wrongly-flags track spans 0-20%, so the 5% limit is visible.
    document.getElementById("frr-bar").style.width = `${Math.min(row.false_reject_rate / 0.2, 1) * 100}%`;
    document.getElementById("frr-value").textContent =
      `${pct(row.false_reject_rate)} of good changes (${Math.round(row.false_reject_rate * n_good)} of ${n_good})`;
    document.getElementById("threshold-note").textContent =
      row.false_reject_rate <= FRR_LIMIT
        ? "Within the 5% limit for wrongly flagged good changes. Stricter settings miss more problems."
        : "Over the 5% limit: too many good changes would be flagged.";
  };
  input.addEventListener("input", show);
  show();
}

// ---- Layer 4 tables (moved here from the old always-open page) -------------------------------

function header(row, text, { cols = 1, rows = 1, scope = "col" } = {}) {
  const cell = el("th", text);
  cell.colSpan = cols;
  cell.rowSpan = rows;
  cell.scope = scope;
  row.append(cell);
}

function resultsTable(table, data, questions) {
  const qs = Object.keys(questions);
  const thead = table.createTHead();
  const top = thead.insertRow();
  const sub = thead.insertRow();
  header(top, "Setup", { rows: 2 });
  header(top, "Tells good from bad (1.0 = perfect)", { cols: qs.length, scope: "colgroup" });
  header(top, "At the 0.70 setting", { cols: 2, scope: "colgroup" });
  header(top, "Time p50 / p95", { rows: 2 });
  header(top, "Cost per check", { rows: 2 });
  header(top, "Meets the bar", { rows: 2 });
  for (const q of Object.values(questions)) header(sub, q);
  header(sub, "Wrongly flags");
  header(sub, "Catches");
  const tbody = table.createTBody();
  for (const r of data.runners) {
    const s = r.summary;
    const row = tbody.insertRow();
    if (isJev(r.name)) row.className = "jev";
    header(row, r.name, { scope: "row" });
    const checks = Object.values(r.checks);
    const cells = [
      ...qs.map((q) => fmt(s.concerns[q].auc_pre)),
      pct(s.pre.false_reject_rate),
      pct(s.pre.catch_rate),
      s.latency_ms ? `${secs(s.latency_ms.p50)} / ${secs(s.latency_ms.p95)}` : "not logged",
      usd(s.cost_usd?.per_call),
      `${checks.filter(Boolean).length} of ${checks.length}`,
    ];
    for (const c of cells) row.insertCell().textContent = c;
  }
}

function sweepTable(table, data) {
  const runners = data.runners.filter((r) => r.sweep);
  const thead = table.createTHead();
  const top = thead.insertRow();
  const sub = thead.insertRow();
  header(top, "Setting", { rows: 2 });
  for (const r of runners) header(top, r.name, { cols: 2, scope: "colgroup" });
  for (const _ of runners) {
    header(sub, "Wrongly flags");
    header(sub, "Catches");
  }
  const tbody = table.createTBody();
  runners[0].sweep.forEach((first, i) => {
    const row = tbody.insertRow();
    header(row, first.threshold.toFixed(2), { scope: "row" });
    for (const r of runners) {
      row.insertCell().textContent = pct(r.sweep[i].false_reject_rate);
      row.insertCell().textContent = pct(r.sweep[i].catch_rate);
    }
  });
}

// ---- Charts: drawn the first time their <details> opens (a closed one has no size to draw into) ----

function dotChart(canvas, data, questions) {
  const labels = Object.values(questions);
  const qs = Object.keys(questions);
  const aucs = data.runners.flatMap((r) => qs.map((q) => r.summary.concerns[q].auc_pre)).filter((v) => v !== null);
  const min = Math.min(0.85, Math.floor(Math.min(...aucs) * 20) / 20);
  const note = canvas.closest("details").querySelector("[data-fill=axis-min]");
  if (note) note.textContent = min.toFixed(2);
  const c = new Chart(canvas, {
    type: "scatter",
    data: {
      datasets: data.runners.map((r, i) => ({
        label: r.name,
        data: qs.map((q, y) => ({ x: r.summary.concerns[q].auc_pre, y: y + (i - (data.runners.length - 1) / 2) * NUDGE })),
        ...SHAPES[i % SHAPES.length],
        clip: false,
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
        x: { min, max: 1.0, ticks: { stepSize: 0.05 }, title: { display: true, text: "Tells good from bad" } },
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
            label: (item) => `${item.dataset.label}: ${fmt(item.parsed.x)}`,
          },
        },
      },
    },
  });
  onThemePalette((p) => {
    const context = withAlpha(p.textMuted, 0.55);
    for (const ds of c.data.datasets) {
      ds.backgroundColor = isJev(ds.label) ? p.primary : context;
      ds.borderColor = p.surface;
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

function drawWhenOpened(details, draw) {
  let drawn = false;
  const go = () => {
    if (details.open && !drawn) {
      drawn = true;
      draw();
    }
  };
  details.addEventListener("toggle", go);
  go();
}

// ---- Deep links: #compare, #strictness, #method (and nested ids) open their <details> ----------

function openFromHash() {
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (!target || target.tagName !== "DETAILS") return;
  for (let node = target; node; node = node.parentElement?.closest("details")) node.open = true;
  target.scrollIntoView({ block: "start" });
}

const [sized, pilot] = await Promise.all([
  fetch("data/results.json").then((r) => r.json()),
  fetch("data/pilot-2026-09-24.json").then((r) => r.json()),
]);
fill("fixtures", sized.fixtures_total);
fill("pilot-total", pilot.fixtures_total);
fill("generated", sized.generated);
const head = sized.runners.find((r) => r.name === HEADLINE).summary;
fill("n-good", head.pre.n_good);
fill("n-bad", head.pre.n_bad);
const agree = Object.values(head.concerns).map((c) => c.agreement);
fill("agreement", `${pct(Math.min(...agree))}–${pct(Math.max(...agree))}`);

answer(sized);
ratings(sized);
compare(sized);
strictness(sized);
resultsTable(document.getElementById("sized-table"), sized, QUESTIONS);
resultsTable(document.getElementById("pilot-table"), pilot, PILOT_QUESTIONS);
sweepTable(document.getElementById("sweep-table"), sized);
drawWhenOpened(document.getElementById("compare-chart"), () =>
  dotChart(document.querySelector("#compare-chart canvas"), sized, QUESTIONS),
);
drawWhenOpened(document.getElementById("pilot-chart"), () =>
  dotChart(document.querySelector("#pilot-chart canvas"), pilot, PILOT_QUESTIONS),
);
openFromHash();
window.addEventListener("hashchange", openFromHash);
// site/version.txt says "dev" in git; the Pages workflow overwrites it with `git describe --tags` at deploy.
fetch("version.txt")
  .then((r) => (r.ok ? r.text() : ""))
  .then((v) => {
    const version = v.trim();
    if (!version) return;
    const link = document.getElementById("version");
    link.textContent = version;
    // An exact tag links to its release; "v0.3.0-2-gabc1234" links to the release list.
    if (/^v\d+\.\d+\.\d+$/.test(version)) link.href = `https://github.com/qte77/feelings/releases/tag/${version}`;
  })
  .catch(() => {});
document.body.dataset.ready = "true"; // lets the page check wait for rendering
