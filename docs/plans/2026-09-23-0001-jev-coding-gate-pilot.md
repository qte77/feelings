# 0001 — Jev coding-gate pilot (go / no-go + Python vs BAML)

## Status — read this first

### Start here (handoff, 2026-09-25)

- **State:** `main` is clean.
  - #1–#20 are merged on the fork `qte77/feelings`; release `v0.5.0`.
  - The page is layered (#12): details sit behind `#compare`, `#strictness` and `#method`.
  - Results live at https://qte77.github.io/feelings/.
  - Local run files (`eval/run-*.jsonl`) are gitignored; the page data is committed.
- **Where the answers are:**
  - The sized eval, "Row 10" below: both Jev runners (with and without BAML) pass every
    bar on 184 fixtures.
  - The pilot, "Answers" below.
- **Next, in order:** the "Remaining work" table.
  - Every row is owner-gated, so start by asking the owner. The recommended first ask is
    row 18 (shadow-mode trial).
  - Nothing is agent-only right now.
- **How to work:**
  - Commands are in "Commands"; code locations in "Source map".
  - Rules: one topic branch per change, TDD for Python, and the full gate before any
    push (ruff incl. `S`, pytest, `baml check`/`baml test`, actionlint and zizmor for
    workflow changes, `scripts/check_site.py` for page changes).
  - Squash-merge once green, delete the branches, and strike the plan row in the same PR.
- **Watch-outs:** the list further down. Most often hit:
  - Always pass `-R qte77/feelings`, or `gh` targets upstream.
  - Commit signing can time out: retry, never disable it.
  - Some other clones set `commit.gpgsign=false`: supersede with `cherry-pick -S`.
  - BAML needs `. ~/.baml/env` and `BAML_AGENT_SKILL_CHECK=off`.
  - Scratch folders don't survive sessions; `scripts/check_site.py` is committed.

**Questions this arc answers:**

1. Can Jev act as a fast check on code changes, in the style of
   [Probably](https://github.com/southpolesteve/probably)? It would run before the slow
   checks (tests, lint, CI), and possibly again after them. Answer: go / no-go against the
   bars in "Decisions and defaults".
2. Which way of calling Jev should we adopt: plain Python with `typesafe-sdk`, or BAML
   (nightly)? Both run the same check (same model, same four questions, same fixtures) and
   write the same log format, so `eval/metrics.py` scores them identically.

Nothing is wired into a real workflow until question 1 is "go".

### Answers (2026-09-23, live Jev `jev-1.13.0`, 60 fixtures × k=5)

1. **Smoke-test pass: go to a properly sized eval, not yet to adoption.** Every bar passes
   except two near misses (see "What a pass means"):
   - Repeat agreement on `single_use_abstraction` (below).
   - End-to-end latency for Python: p95 3.15 s vs the 3 s bar (BAML: 2.94 s). The tail is
     on the API side, since both runners see it. Per request the p95 is 1.5 s, which is
     what `metrics.py`'s latency check measures.

   | runner | scope | single-use | dup | tests | FRR | catch | min agreement | max std | per-request p50 / p95 | blocked |
   |---|---|---|---|---|---|---|---|---|---|---|
   | Jev, Python | 0.98 | 0.93 | 0.97 | 0.94 | 0.04 | 0.68 | 0.946 (single-use) | 0.011 | 1.0 / 1.5 s | 4 of 60 |
   | Jev, BAML | 0.98 | 0.93 | 0.97 | 0.93 | 0.04 | 0.68 | 0.911 (single-use) | 0.012 | — | 4 of 60 |

   - **Fails the agreement bar only on `single_use_abstraction`** (0.946 / 0.911 vs 0.95).
     It is also "maybe" 25% of the time after 5 samples. "Used only once" can't really be
     judged from a diff without the rest of the code, so reword or drop that question
     before a larger eval. The other three questions agree 0.98–1.00.
   - **Not a cache:** only 8.5% of (fixture, question) pairs repeat exactly.
   - **Blocked by TypeSafe's Cloudflare WAF (2026-09-23 only):** 4 of 60 fixtures, i.e. 2
     source commits (`aea508b`, `001c65f`), each as both its good and bad version. The 403
     repeated on every try that day, and no obvious trigger pattern (SQL, script, shell,
     path traversal) was present. **On 2026-09-24 the same fixtures went through: 0 errors
     in 300 requests.** So the block was a rule that changed, not something fixed in the
     content. Any real gate must still treat "blocked" as its own outcome (fall back to
     the slow checks, never block the change).
   - **Against the Claude baseline** (k=1): Jev ranks about as well as Haiku, below Sonnet 5
     and Opus 5.5, and blocks fewer good changes than Haiku (4% vs 13%).
     - Compared on Jev's first sample, to match Claude's k=1: AUC 0.98 / 0.94 / 0.97 / 0.93
       (Python), nearly identical to the 5-sample means above.
     - Jev is scored on 56 of the 60 fixtures (the 4 WAF-blocked ones excluded); Claude on
       all 60.
     It is ~15× faster per request, and ~40–110× cheaper per call at list price.
     - **Measured on 2026-09-24:** median 3,227 input tokens per check (899–5,548), which is
       $0.00013 per check at $0.042/M. That covers input only, since no output price is
       published; Jev reports about 80 output tokens.
     - Claude: $0.005–0.014 per check, measured by the CLI.
     - The earlier "≈ $0.00006 from ~1.5k tokens" was an estimate and too low by about 2×.
   - **Re-run 2026-09-24** (both Jev runners, k=5, all 60 fixtures answered; every runner
     now scored on the same 60). This is what the results page shows.
     - Jev AUC, first answer: 0.99 / 0.92 / 0.97 / 0.92 without BAML, and 0.99 / 0.92 /
       0.98 / 0.94 with it.
     - Near misses are still two, but a different pair: good changes wrongly blocked is
       **7% on both runners (bar 5%)**, and repeat agreement on `single_use_abstraction`
       is 0.933 with BAML. Without BAML it's exactly 0.95, so it passes today.
     - Both come from the same weak question. The two good changes rejected per runner
       (`good-09`, plus `good-14` or `good-29`) are rejected only on
       `single_use_abstraction`, one at exactly 0.70, the cut-off. Row 10's reword-or-drop
       covers both.
     - Per-request p95 without BAML: 0.29 s, versus 1.5 s on 2026-09-23 (service-side
       variance).
2. **Python vs BAML: same quality.** The requests are identical (verified), so the scores
   match within noise.
   - End-to-end time for one check, CLI start-up included, 10 runs each:
     - Python: p50 0.90 s, p95 3.15 s. A first series had one 11.7 s outlier that did not
       repeat.
     - BAML: p50 0.86 s, p95 2.94 s.
     - Both see the same 2–3 s tail, which is on the API side.
   - Code: `jev_gate.py` + shared `concerns.py` vs `code_gate.baml`. The BAML side needs the
     nightly toolchain, and the skill-check bypass until `baml agent install` is run.
   - **Decision (owner, 2026-09-23):** use Jev **both with and without BAML**. Keep both
     runners as first-class, and compare every run against the Claude CLI runs on equal
     terms, per row 11.

- **Results page (row 13, qte77/feelings#2, squash-merged 2026-09-24 as `985ae64`):** live at
  https://qte77.github.io/feelings/. The deploy ran in 16 s. The page was checked headlessly in
  light/dark × desktop/phone, locally and live: no console errors, no failed requests, no
  horizontal page scroll. After a new eval run, re-export `site/data/results.json`
  (see Commands); the deploy runs on push to `main`.

- **Row 8, Claude on the 184 (2026-09-25, branch `feat/claude-on-184`):** all five setups
  scored on the same 184 changes and the same four questions. First answer, AUC averaged
  over the four questions:

  | Setup | Avg AUC | Wrongly flags | Catches | p95 | $/check |
  |---|---|---|---|---|---|
  | Jev, without BAML | 0.942 | 1.7% | 78% | 0.28 s | 0.00012 |
  | Jev, with BAML | 0.947 | 1.7% | 79% | — | — |
  | Claude Haiku 4.5 | 0.899 | 11.9% | 79% | 27.9 s | 0.0092 |
  | Claude Sonnet 5 | 0.958 | 0% | 90% | 21.7 s | 0.022 |
  | Claude Opus 5.5 | 0.969 | 0% | 98% | 19.1 s | 0.042 |

  - Jev separates better than Haiku and close to Sonnet and Opus. At the 0.70 cut-off,
    Sonnet and Opus catch more, at about 80–350× the cost and about 70× the time.
  - Claude's times were measured with 8 requests in flight; Claude ran with k=1.
  - The page's Compare section now uses these numbers. The 60-change pilot stays under
    "How we tested it".
- **Decided 2026-09-25 (owner): no CI for this fork** (row 14 struck). The local gate before every push stays the rule; see "How to work" in Start here.
- **Owner decisions (2026-09-25).**
  - Row 18: go in analyze-stock-kpi.
  - Row 19: the full browser.
  - Row 9: Codex, Gemini CLI, opencode and HarnessRouter.
  - Row 12: an issue first at BoundaryML/feelings. Upstream Probably (southpolesteve/probably) is an MIT toy language with no evaluation and no outside PRs, so it's not a code target.
  - Rows 8 and 14: approved.
  - Row 15: **don't file** (struck).
  - Row 16: wait for the trial.
  - Row 17: still blocked on the owner's branches.
- **Page follow-up (branch `feat/site-version-and-questions`):**
  - The footer shows the deployed version (`git describe --tags` into `site/version.txt`), and a published release redeploys.
  - The Chart.js mention is removed; its licence file still ships.
  - Each rating opens to its exact question, which the export now carries from `concerns.py`.
  - The status line is clearer.
- **Release `v0.5.0` (2026-09-25):** the hero names Jev's typed questions, a new `#alternatives` section (pros and cons measured here; abide and jev-ultrafast build on Jev; Laya not measured yet), and ROC-AUC explained (#20).
- **Release `v0.4.1` (2026-09-25):** a clearer hero (#18): it defines problem changes and clean changes, and spans the full width. Also no Pages release trigger (#17).
- **Release `v0.4.0` (2026-09-25):** Claude on the same 184 changes (#16), the version in the footer, exact questions per rating (#14), and the upstream drafts (#15).
- **Release `v0.3.0` (2026-09-25):** the layered results page (#12).
- **Page redesign (row 21, qte77/feelings#12, squash-merged as `76ad87e`, live and checked):**
  - Layered page: an answer up top and plain-language tiles and ratings, with the detail
    behind three closed questions. Nothing was removed; the full tables and charts moved
    into "How we tested it".
  - Computed from the data: Jev is about 60× faster than the fastest Claude and about 40×
    cheaper than the cheapest (Haiku).
- **Release `v0.2.0` (2026-09-25):** the sized eval (#8), brand favicon (#9) and docs
  (#6, #7, #10) since `v0.1.0`. Notes are in the GitHub release.
- **Release `v0.1.0` (2026-09-24):** the first tag on the fork. It covers #1–#5 and has no
  version file or changelog (none exist upstream either); the notes are in the GitHub
  release.

- **Row 10, sized eval (2026-09-25, qte77/feelings#8, squash-merged as `de9b4ec`; the page's
  favicon followed in #9): both Jev runners pass every
  bar on 184 fixtures** (59 good; bad 30 / 37 / 30 / 32 for weakened tests / unused
  abstraction / duplication / scope creep). Runs: k=5, 0 errors.
  - AUC, first answer, without BAML / with BAML:
    - Scope creep: 0.906 / 0.906.
    - Unused abstraction: 0.894 / 0.911.
    - Duplication: 0.982 / 0.983.
    - Weakened tests: 0.987 / 0.990.
  - Agreement: 0.967–0.995. Good changes wrongly blocked: 1.7% on both (1 of 59, good-51).
    Caught: 78% / 79%.
  - Scope creep and unused abstraction score lower than on the original 60 (0.99 / 0.93).
    The new repos are harder, doc-pipeline-engine most of all (0.81–0.84 on its 28).
  - Cost: median 2,711 input tokens per check, $0.107 for the 920 requests without BAML.
    Row 10's total Jev spend ≈ $0.26 (the reword run plus both 184 runs), against ≈ $0.20
    approved.
  - **Good-label audit:** two real commits add an abstraction nothing else in their diff
    uses, and were relabelled by a rule applied to all 61 goods regardless of model scores
    (`eval/fixtures.README.md`). Before the audit the rate was 4.9%; 2 of those 3
    rejections were Jev being right.
  - **Threshold: keep `REJECT_AT` = 0.70.** Sweep, first answer, wrongly blocked / caught,
    without BAML (with BAML):
    - 0.60: 6.8% / 83% (3.4% / 82%)
    - 0.65: 1.7% / 82% (3.4% / 82%)
    - 0.70: 1.7% / 78% (1.7% / 79%)
    - 0.80: 1.7% / 65%
    - 0.90: 0% / 26%

    0.65 would catch ≈ 3 points more, but it was picked on the same set it's scored on, and
    it doubles the BAML false-reject rate. Revisit on a held-out set.

- **Row 10a, reword decision (2026-09-25): keep the question, reworded; don't drop it.**
  - Old: "Does this change introduce an abstraction (class, interface, helper function, or
    config parameter) that is used only once?"
  - New: "Does this change add a class, interface, helper function, or config parameter
    that nothing else in the diff uses?" The key `single_use_abstraction` is unchanged;
    the page label is now "Unused abstraction".
  - Result on the same 60, Jev without BAML, k=5 (`eval/run-python-reword.jsonl`):
    - AUC, first answer: 0.921 → 0.939.
    - Agreement: 0.950 → 0.967.
    - Still "maybe" after 5 runs: 30% → 13%.
    - Good changes wrongly blocked: 6.7% → 0%.
    - Caught: 70% → 77%.
    - **Every bar passes.** The other questions held or improved: 0.98 / 0.98 / 0.95.
  - All 8 bad fixtures fit the new wording: see `eval/fixtures.README.md`.

- **Fair comparison (row 11, qte77/feelings#4, squash-merged 2026-09-24 as `b19ab5f`):**
  - Jev token usage and input cost logged per request.
  - Every runner scored on the fixtures all runs answered.
  - Page gains "scored on N" and a cost-per-check column.
  - Claude's end-to-end timing moved to owner-gated row 8.

- **Shipped (qte77/feelings#1 on the fork, squash-merged 2026-09-24 as `af08d0c`):**
  - Rows 5–7: key provided 2026-09-23. Spend is estimated at ≈ $0.04 at list price (600
    requests × ~1.5k tokens; usage isn't logged). Live evals, timing and decisions above.
    Blocked requests are recorded and skipped.
  - Row 1: metrics, with tests.
  - Row 2: Python runner, with tests against a fake Jev server (no key, no spend).
  - Row 4: 60 labelled fixtures from `analyze-stock-kpi` (public, Apache-2.0). Leak-scrubbed:
    10 bad records named their own problem and were reworded. Spot-checked by hand: bad-01,
    05, 10, 15, 24. A dry run of all 60 through the runner and metrics with random fake
    answers gave AUC ≈ 0.5 and "no-go", as it should.
  - Row 3: BAML runner compiles and passes offline tests on toolchain
    `0.20.2-nightly.20260922.a`. `CheckDiff@build_request` produces a body identical, as
    parsed JSON, to the Python runner's request for the same fixture.
    `eval_gate -- --k 0` parses all 60 fixtures (extra keys are ignored).
- **Next, in order:** the remaining-work table below.
- **The loop:** agent-only rows first (Phase A). Then one owner sitting for the access
  checklist (Phase B). Then the agent runs both evals and reports (Phase C).
- **Owner gates:**
  - Row 8: OK session usage for the Claude k=5 run (≈ 900 calls, ≈ $8 list).
  - Row 9: pick which harnesses to sweep.
  - (The Jev key was provided 2026-09-23, after sign-ups had been full earlier that day.)
- **Meanwhile: Claude baseline (row 8).** `eval/claude_gate.py` asks the same four questions
  (shared via `eval/concerns.py`) through the logged-in Claude Code session: `claude -p`,
  no API key. Compared against Jev in "Answers" above.
  - **Light results (k=1, 8 workers, corrected fixtures, 2026-09-23).** Post AUC per concern;
    FRR = pre-check false rejects on good fixtures; catch = pre-check rejects on bad
    fixtures; cost is list price (`total_cost_usd`), counted against session usage limits:

    | model (`model_used`) | scope | single-use | dup | tests | FRR | catch | p50 / p95 | cost / 60 |
    |---|---|---|---|---|---|---|---|---|
    | `claude-haiku-4-5-20251001` | 0.99 | 0.91 | 0.97 | 0.96 | 0.13 | 0.73 | 15 / 21 s | $0.32 |
    | `claude-sonnet-5` | 0.99 | 0.99 | 0.96 | 1.00 | 0.00 | 0.87 | 14 / 18 s | $0.38 |
    | `claude-opus-5-5` | 0.99 | 1.00 | 1.00 | 1.00 | 0.00 | 0.97 | 19 / 23 s | $0.84 |

    - **Read with care:** k=1, 60 fixtures, synthetic mutations (see "What a pass means").
      Agreement/spread are not measured at k=1. No model is near the 3 s latency bar
      under 8-way load; a solo Haiku call took 6.7 s.
  - **Earlier Claude numbers are invalid; don't reuse them.** Three bugs inflated or
    contaminated them, all fixed in `claude_gate.py` and each covered by a test:
    1. `claude -p` read the inherited stdin (the whole fixtures file, labels included)
       into every prompt. Fixed with `stdin=DEVNULL`.
    2. User settings added a Fable "advisor" and `effortLevel: xhigh` to every call (~95% of
       cost, ~7× slower). Fixed with `--setting-sources project,local`.
    3. Thinking on cost ~5k tokens per call. Fixed with
       `--settings {"alwaysThinkingEnabled": false}`.
  - **Fixture fix:** 6 of 7 `weakened_tests` mutations left no trace in the diff and were
    unjudgeable (every model scored 0.56–0.84 before the fix). See `eval/fixtures.README.md`.
  - **Caveat:** Claude states a number when asked; Jev returns a classifier probability.
    Compare on AUC (ranking), not on the 0.70 cut-off.
- **Watch-outs:**
  - The BAML skill lives **once**, in `.claude/skills/baml-core/`. The duplicate
    `.agents/skills/` copy was removed on 2026-09-24, and `.gitignore` keeps it and
    `baml-old_skills/` out. `baml agent install` rewrites both locations, so after a
    refresh commit only `.claude/`.
    - Verified in a scratch clone: `baml check --agent-skill-check require` passes with
      only the `.claude/` copy.
    - A symlink doesn't help: `baml agent install` replaces it with a real folder.
    - Both copies come from upstream (`206ddad`, BoundaryML, 2026-09-19), and
      `upstream/main` still has both. So this is a deliberate difference from upstream.
      If an upstream sync changes `.agents/skills/baml-core/SKILL.md`, git reports a
      modify/delete conflict; resolve it by keeping the deletion.
  - `baml` refuses to run while that skill file (written for `0.20.1`) doesn't match the
    toolchain. Until `baml agent install` refreshes it (a separate chore commit), prefix
    commands with `BAML_AGENT_SKILL_CHECK=off`.
  - The Python ↔ BAML question text is enforced by `eval/test_jev_gate.py::test_questions_match_the_baml_version_exactly`.
    Change the questions in both files together.
  - Jev's docs say nothing about caching or determinism. `zero_std_share` near 1.0 means
    repeats come back identical. Suspect a server-side cache before trusting agreement.
  - A classifier probability is a ranking signal, not a calibrated truth. Tune thresholds on
    this data.
  - `typesafe-sdk` default timeout is 10 s (`typesafe_sdk.constants.DEFAULT_TIMEOUT`).

### Commands

```sh
# offline gates
uvx ruff check eval/ && uvx ruff format --check eval/
uv run --no-project --with pytest --with typesafe-sdk pytest eval/ -q --rootdir eval
. "$HOME/.baml/env"; export BAML_AGENT_SKILL_CHECK=off  # see watch-outs
baml check && baml test && baml fmt baml_src/code_gate*.baml

# Phase C — live (needs TYPESAFE_API_KEY in .env)
set -a; source .env; set +a
uv run eval/jev_gate.py 5 < eval/fixtures.jsonl > eval/run-python.jsonl
baml run eval_gate < eval/fixtures.jsonl > eval/run-baml.jsonl
uv run eval/metrics.py eval/run-python.jsonl eval/fixtures.jsonl
uv run eval/metrics.py eval/run-baml.jsonl eval/fixtures.jsonl
# Claude baseline through the logged-in session (no key): [k] [model] [workers]; recorded runs used k=1
uv run eval/claude_gate.py 1 haiku 8 < eval/fixtures.jsonl > eval/run-claude-haiku.jsonl
uv run eval/claude_gate.py 1 claude-sonnet-5 8 < eval/fixtures.jsonl > eval/run-claude-claude-sonnet-5.jsonl
uv run eval/claude_gate.py 1 claude-opus-5-5 8 < eval/fixtures.jsonl > eval/run-claude-claude-opus-5-5.jsonl
# end-to-end time for one check (start-up included), 10 runs each, on good-14 (the fixture timed on 2026-09-23)
grep '"id": "good-14' eval/fixtures.jsonl > eval/one.jsonl
for i in $(seq 10); do /usr/bin/time -f %e uv run eval/jev_gate.py 1 < eval/one.jsonl > /dev/null; done
for i in $(seq 10); do /usr/bin/time -f %e baml run eval_gate -- --k 1 < eval/one.jsonl > /dev/null; done
# more fixtures (row 10): one good + three bad per source commit, used commits skipped
uv run eval/fixtures_build.py eval/fixtures.jsonl 31 31 \
  ../polyfetch-scrape=qte77/polyfetch-scrape ../Agents-eval=qte77/Agents-eval \
  ../doc-pipeline-engine=qte77/doc-pipeline-engine ../analyze-stock-kpi=qte77/analyze-stock-kpi > new.jsonl
# results page data (committed; CI can't run evals). The deploy runs on push to main.
# Sized eval (both Jev runners on all 184); the 2026-09-24 pilot is frozen in site/data/pilot-2026-09-24.json.
uv run eval/metrics.py --export site/data/results.json eval/fixtures.jsonl \
  "Jev, without BAML=eval/run-python-184.jsonl" "Jev, with BAML=eval/run-baml-184.jsonl"
# Don't export Claude's 60-fixture runs alongside: export() keeps only fixtures every run answered.
python3 -m http.server 8137 --directory site   # preview at http://localhost:8137/
uv run --directory ../polyfetch-scrape python ../feelings/scripts/check_site.py <out_dir> [url]  # e2e page check
# release: tag the merge commit (full sha), then redeploy from main so the footer shows the tag
gh release create vX.Y.Z -R qte77/feelings --target <full-sha> --notes-file notes.md
gh workflow run gh-pages.yaml -R qte77/feelings --ref main   # the Pages env only allows main
```

### Arc-start access checklist (owner, once)

| Need | Why | Status |
|---|---|---|
| `baml` CLI, nightly toolchain | BAML runner. Installer: `curl -fsSL https://pkg.boundaryml.com/install.sh \| sh -s` (boundaryml.com/quickstart), then `baml toolchain use nightly && baml toolchain update`. BAML's Jev client is nightly-only ("first be available in the next nightly", boundaryml.com/blog/typesafe-ai-jev) | done 2026-09-23 by owner: wrapper 0.2.5, toolchain `0.20.2-nightly.20260922.a`; `. "$HOME/.baml/env"` added to `~/.bashrc` |
| `TYPESAFE_API_KEY` in `.env` | live eval, both runners (the SDK reads the same variable: `typesafe_sdk.constants.API_KEY_ENV`) | open |
| Spend approval ≈ $0.08 | per runner: 60 fixtures × k=5 = 300 requests × ~3k tokens ≈ 0.9M input tokens × $0.042/M ≈ $0.04 | open |

## Approach

### The check

Jev asks four questions in **one request**, one Noul per question. "Yes" always means "problem".
Each is answerable from the commit message + diff alone, because Jev sees only the state:

| field | question (exact text in `eval/jev_gate.py` `CONCERNS`) |
|---|---|
| `scope_creep` | adds functionality beyond what the commit message describes |
| `single_use_abstraction` | introduces an abstraction used only once |
| `duplication` | duplicates logic that appears elsewhere in the same diff |
| `weakened_tests` | weakens, skips, or deletes tests or assertions |

Correctness, security, and numeric/date logic stay with tests and linters. TypeSafe's docs
call Jev "not a calculator".

### Two modes, scored from one eval run

Each fixture is sent k=5 times; `eval/metrics.py` derives both modes from the same log:

- **Pre-check (fast, before the slow checks):** uses the first sample only.
  - **Reject** if any concern has p ≥ 0.70; otherwise let the change through to the slow checks.
  - Asymmetric on purpose: "uncertain" never blocks, and the slow checks stay authoritative.
- **Post-check (after the slow checks pass):** uses all 5 samples, per concern.
  - **Problem** if ≥ 4 of 5 samples are ≥ 0.70.
  - **Clear** if ≥ 4 of 5 are < 0.50.
  - Otherwise **maybe**: send to a human. This mirrors Probably's `otherwise maybe`.

### Python vs BAML comparison

| Axis | How it is measured |
|---|---|
| Same answers? | Metrics from both runs should match within noise. A gap means the two send different requests. Diff the Python request body (`test_jev_gate.py` fake server) against `CheckDiff@build_request`. |
| Speed | End-to-end time for one check, start-up included (commands above). Python also logs per-request `latency_ms`. |
| Code | Lines for the check + runner (`jev_gate.py` vs `code_gate.baml`); dependencies (`typesafe-sdk` vs nightly toolchain). |
| Testability | Both test offline. Python: fake HTTP transport through the real SDK. BAML: `@build_request`. |
| Fit | Target repos (`gha-issue-triage`, `gha-rxiv-paper-eval`, `analyze-stock-kpi`, RDI judges) are Python. |

### Deliberately not built in this arc (YAGNI until "go")

- The `git diff | … gate` hook.
- The refine loop, "while concerns remain and attempts < 3, rewrite": the shape of README §6
  and Probably's bounded `while`.
- A provider-agnostic judge interface.
- **abide** (github.com/coldteadotai/abide, MIT, TypeScript; **deferred 2026-09-25 by the owner**). It enforces a repo's AGENTS.md rules in Claude Code, Codex and OpenCode by asking Jev one question per rule on every edit or turn, and has the agent repair a break. Its README reports catching single-use abstractions and duplicated logic at about 300 ms and a fraction of a cent per check. It honours `TYPESAFE_AI_BASE_URL`, so it could also run against a self-hosted Laya. It's the packaged form of this pilot's idea: revisit when a trial vehicle is chosen (row 18).
- An agent-readiness-kit scan of the page (**deferred 2026-09-25**). The kit takes no
  URL argument (it scans its own `config/properties.ts` list) and grades `llms.txt`,
  `robots.txt` and `/.well-known/` at the domain root, so for `/feelings/` it would grade
  qte77.github.io's root. It also files remediation issues in its own repo. To cover this
  page, add it to that kit's property list instead.

Each becomes a row in the next arc if the result is "go".

### Decisions and defaults (the owner can override at the checkpoint)

| Decision | Default |
|---|---|
| Model | pinned `jev-1.13.0` in both runners (docs.typesafe.ai/models: `jev-latest` → `jev-1.13.0`; "pin that version's ID" once thresholds are tuned). The shared `Jev` client in `vibes.baml` stays on `jev-latest`. |
| Fixture source | `analyze-stock-kpi` history: 30 real commits + 30 single-concern mutations (repo verified public, Apache-2.0, so fixtures are committed). |
| Latency bar | p95 ≤ 3 s for one check, end to end. No latency figure is published by TypeSafe. |
| Pass bars (`eval/metrics.py` `BARS`) | per-concern post AUC ≥ 0.80 · repeat agreement ≥ 95% · mean per-pair std ≤ 0.02 · pre-check false-reject on good fixtures ≤ 5% |
| What a pass means | 60 fixtures is smoke-test scale. A pass means "worth a properly sized, calibrated eval", **not** "calibrated". The false-reject bar on 30 good fixtures is ≤ 1 fixture, so one unlucky sample flips it. Treat a one-fixture miss as "re-run / enlarge", not "no-go". |
| Adopt Python or BAML | **Both** (owner, 2026-09-23): keep both runners first-class. The page's headline numbers use Jev without BAML, since the two agree within 0.02 AUC. |
| Page ratings (Layer 1) | From AUC on the first answer: ≥ 0.95 excellent (5 dots) · ≥ 0.85 good (4) · ≥ 0.80 fair (3, the pass bar) · below 0.80 weak (2). |
| Page ratios (Layers 0 and 2) | Speed: per-request p95 of Jev without BAML against the range of the Claude models in the pilot. Cost: per check against **Claude Haiku 4.5, the cheapest Claude**, so the ratio isn't flattered. Both are computed from the data files and rounded to one significant figure. |

## Source map

| What | Where |
|---|---|
| Metrics + pass bars | `eval/metrics.py` (`summarize`, `post_decision`, `verdict`, `BARS`, `score`, `error_summary`, `export`: several runs → strict JSON, NaN → null, every runner scored on the fixtures all runs answered, `fixtures_scored` next to `fixtures_total`, errors from each full run, plus a per-runner `sweep`; `sweep()`: false rejects and catch per threshold 0.50–0.90 on the first answer); tests `eval/test_metrics.py` |
| Fixture builder | `eval/fixtures_build.py`: mutations `weaken_test` (top-level `==` with a truthy right side only), `add_unused_abstraction`, `add_duplication` (whole function, multi-line signatures), `add_scope_creep` (in-file / new file alternating); `_free` avoids names the diff already uses; `added_by`, `leaks`, `parses` guard every record; `select` serves the scarcest concern; `build`/`candidates` walk git. Tests `eval/test_fixtures_build.py`. Provenance and the good-label audit: `eval/fixtures.README.md` |
| Page check (e2e) | `scripts/check_site.py`, run with polyfetch-scrape's patchright: light/dark × desktop/phone. It asserts the verdict, 3 tiles and 4 ratings; every `<details>` closed on load; all charts drawn once opened; table row counts; the slider updating; deep links (`#strictness`, and nested `#compare-chart` opening its parent); no sideways scroll with everything open. It fails on console/page errors or failed requests. If patchright is updated, run `patchright install chromium` once |
| Results page | `site/index.html`: Layer 0 answer (`#verdict`, `#tiles`), Layer 1 `#ratings`, and `<details>` `#compare` (nested `#compare-chart`), `#strictness`, `#method` (nested `#full-results`, `#full-chart`, `#pilot-results`, `#threshold-table`). `site/app.js`: `answer`, `ratings`, `compare`, `strictness`, `resultsTable`, `sweepTable`, `dotChart` via `drawWhenOpened` (Chart.js can't draw into a closed `<details>`), `openFromHash`; `RATINGS`/`HEADLINE`/`CURRENT_THRESHOLD` per "Decisions". CSS triangles for disclosure markers. Data: `site/style.css`, `site/data/results.json` (sized eval: both Jev runners on 184), `site/data/pilot-2026-09-24.json` (frozen 5-runner pilot on 60); copied in: `site/eyerest.css`, `a11y.css`, `theme.js`, `chart-theme.js` from `qte77/brand/ui-kit`, `site/favicon.svg` = `qte77/brand/images/logo-mark.paths.dejavu.svg` (byte-identical to analyze-stock-kpi's; linked relatively because the site lives under `/feelings/`), `site/vendor/chart.umd.min.js` (Chart.js v4.5.1) from `analyze-stock-kpi`; deploy `.github/workflows/gh-pages.yaml` (pins from `analyze-stock-kpi`). Chart colours: Jev = `--primary`, Claude = `--text-muted` at 55% alpha; the categorical validator doesn't apply to emphasis, but primary vs grey separate by ΔE 22.6 (light) / 27.5 (dark) |
| Python runner | `eval/jev_gate.py` (`MODEL`, `INPUT_USD_PER_M` with its source, `check` → answers + usage, `cost_usd`, `run`, which writes `input_tokens`/`output_tokens`/`cost_usd` per record, records `TypeSafeAPIError` as an `error` record and skips remaining repeats); questions/state come from `eval/concerns.py`; tests `eval/test_jev_gate.py` |
| Shared questions + state | `eval/concerns.py` (`CONCERNS`, `state_for`) |
| Claude baseline runner | `eval/claude_gate.py` (`SCHEMA`, `build_command`, `cli`, `check`, `run(workers=)`); tests `eval/test_claude_gate.py`; args `[k] [model] [workers]`, model defaults to `haiku` (current Haiku), any concrete id pins a version |
| BAML runner | `baml_src/code_gate.baml` (`JevPinned`, `Concerns`, `Fixture`, `Sample`, `Failed`/`failed`, `CheckDiff`, `state_for`, `eval_gate`, which catches `ai.errors.InvalidRequest` → `Failed` record); tests `baml_src/code_gate_test.baml` |
| Lint config for `eval/` | `eval/ruff.toml` |
| Shared Jev client (`jev-latest`) | `baml_src/vibes.baml:87` |
| float field = raw Noul probability; class = one question per field | README §4; boundaryml.com/blog/typesafe-ai-jev |
| Offline request test helper `questions()` | `baml_src/vibes_test.baml:3` (reused by `code_gate_test.baml`) |
| stdin reader (stops at an empty line; fine for JSONL) | `baml_src/grep_with_vibes.baml:19` `read_stdin_lines` |
| Jev API | `POST https://api.typesafe.ai/v1/systemone`; body `{"state", "model", "questions": {name: {"type": "noul", "instructions"}}}` (verified through the SDK against a fake server); a Noul answer returns `noul` in [0, 1] and **no confidence** (docs.typesafe.ai/api) |
| Python SDK | `typesafe-sdk==0.7.1`: `TypeSafeClient(transport=…)`, `.system_one(state, questions, model=)`, `response.nouls[name].noul`; reads `TYPESAFE_API_KEY`; default timeout 10 s |
| Jev limits (vendor-reported) | 64k tokens per request; 32k for state + the longest question; 1,200 req/min; $0.042 per 1M input tokens (docs.typesafe.ai/models) |
| Reference designs | Probably: bounded `while` (≤ 5 iterations), confidence gates with `otherwise maybe`, fake providers in tests (github.com/southpolesteve/probably) |

### Harness sweep: research (2026-09-23, subagent; unverified points marked)

- **HarnessRouter** (github.com/HarnessRouter/harnessrouter, Apache-2.0, created 2026-08-09,
  very active). Verified via the GitHub API.
  - A self-hosted (Docker) or cloud HTTP gateway in front of many agent CLIs: Claude Code,
    Codex, Gemini CLI, OpenCode, Aider, … Requests look like the OpenAI Responses API
    (`POST /{harness_id}/v1/responses`) and can be one-shot (`"stream": false`).
  - **Unverified:** JSON-schema structured output (the protocol spec page returned 404);
    auth other than API keys (host logged-in sessions); cost/latency/model fields in
    responses (only marketing claims seen).
  - **Decision (default):** defer. Without structured output and session-auth parity, its
    rows wouldn't be comparable with `claude_gate.py`. Revisit when those are confirmed.
- **`coding-harness-eval`** (`/workspaces/qte77/coding-harness-eval`,
  `github.com/qte77/coding-harness-eval`). It was renamed from `coding-agent-eval`: GitHub
  confirmed the new name via its API on 2026-09-23. The local folder, git remote and
  Claude Code project data were renamed the same day. The in-repo rename merged on
  2026-09-25 as qte77/coding-harness-eval#55. It superseded #54, whose commit was
  unsigned because that clone has `commit.gpgsign=false` set locally.
  - Rename references in other repos: ai-agents-research#484 and
    cc-recursive-team-mode#19 are merged.
  - The remaining rename work is row 17.
  - It grades task execution by agents (CC, Cline, opencode, Codebuff, Antigravity).
  - Only graders exist so far. Runners/collectors are still pending, so there are no
    adapters to reuse.
- **Decision (default):** harness runners live in `feelings/eval/`, next to the fixtures,
  metrics and JSONL contract. `coding-harness-eval` solves a different problem.

## Remaining work

| # | Item | Gate | Done when |
|---|---|---|---|
| 12 | Upstream contribution to `BoundaryML/feelings` (issue first, owner 2026-09-25). **Pre-staged:** branch `contrib/code-review-example` on our fork (1 commit on `upstream/main`: `baml_src/code_review.baml`, a `Review` class answered by one `.fill<Review>()`, piped from `git diff` via upstream's `read_stdin_lines()`; `code_review_test.baml`; README section 8 with measured results and the question-wording tip). `baml test`: 6 passed; one live run on a real diff returned four low scores. Drafts: `docs/upstream/2026-09-25-boundaryml-issue.md` and `…-pr.md`. Keep the branch: it is the PR head. Probably (southpolesteve/probably) is not a code target. | owner: approve posting the issue draft (public); the PR only after the maintainers say yes | Issue posted; the PR opened or dropped per their answer; the branch deleted when resolved |
| 16 | Jev fit across the owner's 21 repos: a survey by subagents on 2026-09-23, recorded here so it isn't lost. Recommended order: (1) generalise `feelings/eval` into a shared judge harness (questions, labelled fixtures, metrics, swappable provider); (2) move the shared Actions `gha-issue-triage` and `gha-rxiv-paper-eval` from hand-parsed LLM text to a fixed JSON output, then Jev as a provider; (3) vertical pilots on public text (CorinItemPhotoSales sold-listings filter, then ldnmxx fallback routing); (4) build-behind-gate for coding-harness-eval's solution grader. No-go, on purpose: pseudonymize-text (PII), m365dsc control checks (tenant data), claude-azure-workflows-gui production (EU in-tenant), doc-pipeline-engine (Jev rejected, issue #196), a2ui-agui-kit guard, vlm-toolkit triage (free today). The findings came from subagent reads and haven't been re-verified here. | owner: wait for the row 18 trial (owner, 2026-09-25) | Owner decides; if started, a new plan file `docs/plans/YYYY-MM-DD-NNNN-jev-estate-rollout.md` takes this row over |
| 17 | Finish the `coding-agent-eval` → `coding-harness-eval` rename references in 4 repos. Three are on other branches with the owner's unpushed work: `.github-private-project-tracker` (`repos.txt`, the one that matters), `ldnmxx` (plus 4 untracked files) and `qte77.github.io`. `2026-06-job-research` has no GitHub remote. | owner: land or park those branches first; for the local-only repo, say whether a local commit is wanted | Each repo updated through a signed, squash-merged PR (or a local commit for the local-only repo), or explicitly dropped |
| 9 | Harness sweep: one thin runner per coding harness (Codex, Gemini CLI, opencode, …) in `eval/`, same pattern as `claude_gate.py`. See "Harness sweep: research (2026-09-23)". | agent: the owner picked **Codex CLI, Gemini CLI, opencode and HarnessRouter** (github.com/HarnessRouter/harnessrouter), 2026-09-25. Each needs its own login or key on this machine; ask for any that are missing | Each runner: headless flags, structured-output mode and settings isolation taken from that CLI's own docs (not memory); `stdin=DEVNULL`; offline tests; one live smoke call; records in the shared JSONL format |
| 18 | **Question 1, go / no-go.** The sized eval passes every bar for both runners. Recommended next step: a **shadow-mode trial** in one real repo's CI, where Jev scores each PR's diff, posts the four probabilities as a check summary and **never blocks**; compare against human review for a few weeks. It opens the arc's "Deliberately not built" items (the diff hook, a judge interface). Caveats: synthetic mutations, filter-based good labels for 59 fixtures, and no Claude comparison on the 184 yet (row 8). | owner, 2026-09-25: **no Jev check in CI for now**, and **abide deferred** (documented under "Deliberately not built"). The earlier "go in analyze-stock-kpi" is on hold, and the secret is not set. Open question: run the check **locally** first (a non-blocking `pre-push` hook), see row 24 | Owner re-opens with a vehicle (a local hook, CI, or abide); then a new arc plan `docs/plans/YYYY-MM-DD-0002-jev-shadow-trial.md` takes this row over |
| 19 | Example browser on the page, in analyze-stock-kpi's style: a table of all 184 fixtures with each runner's first-answer scores, and fuzzy search (Fuse.js v7.0.0, vendored like analyze-stock-kpi's `ui/public/vendor/fuse.min.js` + Apache-2.0 `LICENSE`) over `message`, `source_repo` and `id`. Label chips filter exactly; the diff opens on expand. State lives in the URL (`q`, `label`, `repo`, `runner`, `sort`) via a pure `state.js`, copying analyze-stock-kpi's `ui/lib/state.js` pattern: defaults dropped, `history.replaceState`, unknown params kept. That pattern's tests run with `node --test` (no npm here). | agent: the owner chose the **full browser** (2026-09-25); it goes in the layered page as an `#examples` section | `state.js` tested first; the export writes per-fixture scores to `site/data/`; `scripts/check_site.py` covers search and deep links |
| 20 | Suspected bug in analyze-stock-kpi, found while reading it on 2026-09-25 and **not verified**: `ui/app.js:689` parses URL state with the fallback universe list before `populateUniversePicker` (l.700) loads `universes.json`, so deep links to universes outside that list may be dropped. | agent verifies with a headless deep-link test; owner approves the issue or PR in that repo | Reproduced (or disproved) with a URL; an issue or fix PR opened there only after approval |
| 22 | Tracked in **qte77/feelings#24** (issues enabled on the fork 2026-09-25). Measure **Laya** (github.com/NandhaKishorM/laya, Apache-2.0, open weights, self-host only, CPU 193–464 ms/question per its README) on the same 184 fixtures and questions. **Free routes (research 2026-09-25, subagent, sources in the chat log):** (a) a **manual GitHub Actions batch run** on this public repo: free, 4 vCPU/16 GB, 6 h/job, weights cached, Laya run in-process, results as an artifact. It works for evaluating this project, but **not as an always-on server**: GitHub's terms bar "part of a serverless application" and activity "unrelated to" the repo. (b) Your own **HF ZeroGPU Space**: free, 5 GPU-min/day, Gradio wrapper needed. (c) **Modal**: $30/mo credit, but a card is needed. (d) Local, blocked by disk. No hosted API exists, and HF Inference Providers and LLM-catalogue providers (Cerebras, Groq, Cloudflare Workers AI and others) can't serve it. | owner: pick a route; (a) conflicts with "no CI for this fork" unless run only by hand as an eval job | `eval/run-laya-184.jsonl` exported next to Jev and Claude; the page's alternatives section says pro or con from measured numbers |
| 23 | Add **PR-AUC** (rare-class precision: 30–37 positives against 147–154 negatives per question) and the **Brier score** (calibration; the check acts on a fixed 0.70) to `summarize()`, written test-first. Show them in "How we tested it" next to ROC-AUC. No new runs: the existing run files suffice. | agent | Tests written first; values for all 5 setups in `results.json`; the page's "Why ROC-AUC" note updated |
| 24 | **Local Jev check before CI** (proposed 2026-09-25): a small `scripts/jev_check.py` reusing `eval/jev_gate.check()` and `eval/concerns.py`, run by an opt-in, **non-blocking** git `pre-push` hook on the outgoing diff. It prints the four probabilities and a "worth a closer look" note at ≥ 0.70, and exits 0 even on an API error or a firewall block. About $0.0001 and 0.3 s per push; it needs `TYPESAFE_API_KEY` locally, which is already in `.env`. | owner: yes/no | Hook installed with one command and documented; tested first with a fake transport; a log of real pushes to compare later with review findings |
