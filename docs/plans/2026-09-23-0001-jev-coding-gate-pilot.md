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

- **Shipped (branch `feat/jev-coding-gate-pilot`, not yet merged):**
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
- **Owner gates:** provide `TYPESAFE_API_KEY`, approve spend of about $0.08 (two runners).
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
| Python runner | `eval/jev_gate.py` (`CONCERNS`, `MODEL`, `state_for`, `check`, `run`); tests `eval/test_jev_gate.py` |
| BAML runner (uncompiled) | `baml_src/code_gate.baml` (`JevPinned`, `Concerns`, `CheckDiff`, `state_for`, `eval_gate`); tests `baml_src/code_gate_test.baml` |
| Lint config for `eval/` | `eval/ruff.toml` |
| Shared Jev client (`jev-latest`) | `baml_src/vibes.baml:87` |
| float field = raw Noul probability; class = one question per field | README §4; boundaryml.com/blog/typesafe-ai-jev |
| Offline request test helper `questions()` | `baml_src/vibes_test.baml:3` (reused by `code_gate_test.baml`) |
| stdin reader (stops at an empty line; fine for JSONL) | `baml_src/grep_with_vibes.baml:19` `read_stdin_lines` |
| Jev API | `POST https://api.typesafe.ai/v1/systemone`; body `{"state", "model", "questions": {name: {"type": "noul", "instructions"}}}` (verified through the SDK against a fake server); a Noul answer returns `noul` in [0, 1] and **no confidence** (docs.typesafe.ai/api) |
| Python SDK | `typesafe-sdk==0.7.1`: `TypeSafeClient(transport=…)`, `.system_one(state, questions, model=)`, `response.nouls[name].noul`; reads `TYPESAFE_API_KEY`; default timeout 10 s |
| Jev limits (vendor-reported) | 64k tokens per request; 32k for state + the longest question; 1,200 req/min; $0.042 per 1M input tokens (docs.typesafe.ai/models) |
| Reference designs | Probably: bounded `while` (≤ 5 iterations), confidence gates with `otherwise maybe`, fake providers in tests (github.com/southpolesteve/probably) |

## Remaining work

| # | Item | Gate | Done when |
|---|---|---|---|
| 5 | Key + spend approval | owner | `.env` has `TYPESAFE_API_KEY`; ≈ $0.08 approved |
| 6 | Live eval, both runners + go / no-go | agent | `eval/run-python.jsonl` and `eval/run-baml.jsonl` each have 300 records; `metrics.py` output for both pasted here; each pass bar marked pass/fail |
| 7 | Speed + code comparison and adoption decision | agent | 10 timed single-check runs per runner (p50/p95); comparison table filled in; decision recorded in this Status section |
