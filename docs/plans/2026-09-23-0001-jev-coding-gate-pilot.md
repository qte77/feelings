# 0001 — Jev coding-gate pilot (go / no-go + Python vs BAML)

## Status — read this first

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
   - **Blocked by TypeSafe's Cloudflare WAF:** 4 of 60 fixtures, i.e. 2 source commits
     (`aea508b`, `001c65f`), each as both its good and bad version. The 403 happens every
     time, on content alone, and no obvious trigger pattern (SQL, script, shell, path
     traversal) is present. Any real gate must treat "blocked" as its own outcome
     (fall back to the slow checks, never block the change).
   - **Against the Claude baseline** (k=1): Jev ranks about as well as Haiku, below Sonnet 5
     and Opus 5.5, and blocks fewer good changes than Haiku (4% vs 13%).
     - Compared on Jev's first sample, to match Claude's k=1: AUC 0.98 / 0.94 / 0.97 / 0.93
       (Python), nearly identical to the 5-sample means above.
     - Jev is scored on 56 of the 60 fixtures (the 4 WAF-blocked ones excluded); Claude on
       all 60.
     It is ~15× faster per request, and an estimated ~50–200× cheaper per call at list
     price: ≈ $0.00006 (about 1.5k input tokens × $0.042/M; the runner does not log usage)
     vs $0.005–0.014 measured for Claude.
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

- **Shipped (branch `feat/jev-coding-gate-pilot`, not yet merged):**
  - Rows 5–7: key provided 2026-09-23. Spend is estimated at ≈ $0.04 at list price (600
    requests × ~1.5k tokens; usage isn't logged). Live evals, timing and decisions above. Blocked requests are recorded and skipped (`0fb11da`).
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
  - `baml` refuses to run while the repo's BAML skill files (`.claude/skills/baml-core/`,
    `.agents/skills/baml-core/`, written for `0.20.1`) don't match the toolchain. Until
    `baml agent install` refreshes them (a separate chore commit), prefix commands with
    `BAML_AGENT_SKILL_CHECK=off`.
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
# end-to-end time for one check (start-up included), 10 runs each
head -1 eval/fixtures.jsonl > eval/one.jsonl
for i in $(seq 10); do /usr/bin/time -f %e uv run eval/jev_gate.py 1 < eval/one.jsonl > /dev/null; done
for i in $(seq 10); do /usr/bin/time -f %e baml run eval_gate -- --k 1 < eval/one.jsonl > /dev/null; done
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

Each becomes a row in the next arc if the result is "go".

### Decisions and defaults (the owner can override at the checkpoint)

| Decision | Default |
|---|---|
| Model | pinned `jev-1.13.0` in both runners (docs.typesafe.ai/models: `jev-latest` → `jev-1.13.0`; "pin that version's ID" once thresholds are tuned). The shared `Jev` client in `vibes.baml` stays on `jev-latest`. |
| Fixture source | `analyze-stock-kpi` history: 30 real commits + 30 single-concern mutations (repo verified public, Apache-2.0, so fixtures are committed). |
| Latency bar | p95 ≤ 3 s for one check, end to end. No latency figure is published by TypeSafe. |
| Pass bars (`eval/metrics.py` `BARS`) | per-concern post AUC ≥ 0.80 · repeat agreement ≥ 95% · mean per-pair std ≤ 0.02 · pre-check false-reject on good fixtures ≤ 5% |
| What a pass means | 60 fixtures is smoke-test scale. A pass means "worth a properly sized, calibrated eval", **not** "calibrated". The false-reject bar on 30 good fixtures is ≤ 1 fixture, so one unlucky sample flips it. Treat a one-fixture miss as "re-run / enlarge", not "no-go". |
| Adopt Python or BAML | Python, unless BAML is clearly better on the comparison table. The adoption targets are Python, and BAML's Jev support is nightly-only. |

## Source map

| What | Where |
|---|---|
| Metrics + pass bars | `eval/metrics.py` (`summarize`, `post_decision`, `verdict`, `BARS`); tests `eval/test_metrics.py` |
| Python runner | `eval/jev_gate.py` (`MODEL`, `check`, `run`, which records `TypeSafeAPIError` as an `error` record and skips remaining repeats); questions/state come from `eval/concerns.py`; tests `eval/test_jev_gate.py` |
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
  Claude Code project data were renamed the same day; the in-repo rename is
  qte77/coding-harness-eval#54.
  - It grades task execution by agents (CC, Cline, opencode, Codebuff, Antigravity).
  - Only graders exist so far. Runners/collectors are still pending, so there are no
    adapters to reuse.
- **Decision (default):** harness runners live in `feelings/eval/`, next to the fixtures,
  metrics and JSONL contract. `coding-harness-eval` solves a different problem.

## Remaining work

| # | Item | Gate | Done when |
|---|---|---|---|
| 11 | Fair comparison across runners (Jev without BAML, Jev with BAML, Claude CLI; optionally Claude through BAML, which needs `ANTHROPIC_API_KEY`) | agent (Claude through BAML: owner provides the key) | `metrics.py` takes several run files and scores them on the **same answered fixtures**, reporting first-sample and k-sample metrics side by side; one timing method for all runners (10 single CLI calls, start-up included); Jev token usage logged |
| 12 | Upstream contribution to `BoundaryML/feelings`: our fork's `main` is identical to upstream's, upstream has had no PRs yet, and its open issue #1 is "No LICENSE file". Candidate: a small BAML-only PR (standalone `code_gate.baml` shell tool + offline tests + README section, results summarised in the PR text) and/or an issue about the WAF 403s. `eval/` and `docs/plans` stay in the fork. | owner: deferred ("not now", 2026-09-23) | Owner decides the scope; then the PR is cut from upstream `main`, not from this branch |
| 10 | Properly sized eval: reword or drop `single_use_abstraction`; more fixtures (≥ 30 per concern, from more than one repo); log `usage.input_tokens` per request for real cost | agent (fixture sourcing from other repos = data) | New question set passes the agreement bar; per-concern AUC holds on the larger set; blocked rate reported; cost measured, not estimated; reject threshold tuned (catch is 0.68 at the untuned 0.70 despite AUC 0.93–0.98); blocked-run test covers k>1 |
| 8 | Claude repeat run (k=5) for agreement/spread; light k=1 run shipped, results in Status | owner OKs session usage (≈ 900 calls for 3 models, ≈ $8 list) → agent | `run-claude-<model>.jsonl` has 300 records per model; agreement/spread rows added to the Status table |
| 9 | Harness sweep: one thin runner per coding harness (Codex, Gemini CLI, opencode, …) in `eval/`, same pattern as `claude_gate.py`. See "Harness sweep: research (2026-09-23)". | agent (after owner picks the harnesses) | Each runner: headless flags, structured-output mode and settings isolation taken from that CLI's own docs (not memory); `stdin=DEVNULL`; offline tests; one live smoke call; records in the shared JSONL format |
