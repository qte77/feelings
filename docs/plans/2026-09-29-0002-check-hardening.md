# 0002 — Harden, verify and rerun the Jev code-change check

## Start here (handoff, 2026-09-29)

**What this arc is for:**
- **Verify** the check the pilot built (plan 0001, closed): is it reproducible, does it hold without cues from how the fixtures were built, are the labels right, and how noisy are the numbers?
- **Improve** it only where the verification shows it's needed.
- **Rerun** everything behind one command, then publish.

**Already known** (0001, releases up to v0.8.0; baseline = tag `v0.8.0`):
- On 184 labelled changes from the owner's repos, Jev scores 0.89–0.99 ROC-AUC per question, catches 78% of flawed changes and wrongly flags 1 of 59 clean ones.
- On 120 held-out yt-dlp changes, ranking holds (0.91 average), but the 0.70 setting wrongly flags 23–30%. Claude ranks the same (0.92–0.93) but flags fewer clean changes.
- The page is live: https://qte77.github.io/feelings/.

**How to work this plan:**
1. **Read this block, then "Lanes and worktrees".** Pick the next rows from "Remaining work" in phase order. Within a phase, run the rows' lanes **in parallel as subagents, each in its own git worktree**: `Agent` with `isolation: "worktree"`.
2. **The main session orchestrates:**
   - it spawns the lanes;
   - it reviews each lane's PR;
   - it merges the PRs **one at a time** (squash), rebasing the next onto `main`;
   - it alone edits the shared files listed under "Lanes and worktrees".
3. **Each lane:**
   - works on a topic branch in its worktree, test-first for Python;
   - runs the full gate (below);
   - opens a PR with `-R qte77/feelings`;
   - edits **only its own row's line** in the table below: done, with its PR number. Nothing else in this file.
4. **After each merge (main session):** update this block's status, delete the branches, and release if the page or data changed. Then `gh workflow run gh-pages.yaml -R qte77/feelings --ref main` and a live page check.

**Status (2026-09-29):** phase 0 (#36) and phase 1 are done. P4 (#37), P3 (#38), P1 (#39) and P2 (#40) ran as 4 parallel worktree lanes.

**Phase 1 results** (first-answer ROC-AUC; P1 figures are the all-answer mean):
- **P1 · reproducible ranking:** every question and setup is within ±0.009. One sub-check fails: Jev without BAML on yt-dlp wrongly flags 7 of 30 clean changes, against 9 at baseline. The two that changed sat at the 0.70 cutoff, so this is noise there, not drift.
- **P2 · a cue in how fixtures were built:** with the new-file additions moved into existing files, *unused abstraction* drops 0.894 → 0.860 on the 184 and 0.851 → 0.799 on yt-dlp. *Scope creep* on yt-dlp drops 0.821 → 0.774. The fake hunk headers didn't matter. This is a lower bound: 16 of 50 records on the 184 couldn't be moved. **The pre-registered bar is exceeded, so the page's caveat is updated, and P5 comes before phase 2.**
- **P4 · intervals:** Jev catches 78% [71–86%] and wrongly flags 1.7% [0–5.1%]. *Unused abstraction* calibrates poorly: Brier 0.23 and PR-AUC 0.60, against over 0.94 for the others.
- **P3 · label queue:** 8 records are queued for the owner.

**P5 done (2026-10-07, #45).**
- Both fixture sets are settled, so no new-file or fixed-header cue is left, apart from 16 residual records on the 184.
- Jev was rerun on everything. Claude was rerun on the 148 changed records only and merged with checks; see `eval/fixtures.README.md`.
- The page data is re-exported, and the page's "Overstated" caveat is replaced by "Examples fixed".
- **Results** (first-answer ROC-AUC, *unused abstraction* before → after):
  - Jev: 0.89 → 0.84 on the 184 (0.83 without the residuals); 0.85 → 0.78 on yt-dlp.
  - Jev scope creep on yt-dlp: 0.82 → 0.77.
  - Claude moved less: Opus by −0.01, Haiku by −0.03 and −0.07, Sonnet by −0.04 and +0.03.
  - So Jev relied on the cue more than Claude did.
- Jev without BAML now meets 13 of 14 bars on the 184: scope-creep repeat agreement is 0.946 against 0.95 (BAML: 0.967).
- On yt-dlp, Jev's scope creep and unused abstraction (0.77, 0.78) are below 0001's 0.80 bar.

**Next:** phase 2 (E1, E2, E4 as lanes; E3 and E5 gated). Not started: deferred by the owner on 2026-10-07.

**Owner gates, all batched in "Remaining work":**
- Claude spend: about $10 per full rerun of the 3 models on both sets.
- About an hour of label review (P3).
- Whether collecting real flawed commits is worth it (E3).
- The rows carried over from 0001 keep their original gates.

**Where findings go** (one home each; link, don't copy):

| Kind | Home |
|---|---|
| Public numbers | the page and `site/data/*.json`, with a release |
| Method, decisions, bars, next steps | this plan |
| How fixtures were built or changed | `eval/fixtures.README.md` |
| How a baseline model was called | the page's "How Claude was called" and #43 |
| Harness-benchmark rules | qte77/coding-harness-eval#59 |
| Reusable lessons for other projects | qte77/ai-agents-research `docs/non-cc/infrastructure/jev-analysis.md` (update tracked in #622) |

**Watch-outs:**
- **No Docker in this Codespace.** Anything container-based (Harbor, etc.) runs in a manual GitHub Actions job or a cloud sandbox; see qte77/coding-harness-eval#57.
- `gh` and `git push` must run as `env -u GH_TOKEN -u GITHUB_TOKEN …`; the env tokens are stale and give HTTP 401.
- Always pass `-R qte77/feelings`, or `gh` targets upstream BoundaryML.
- Commit signing can time out: retry, never disable it.
- Worktrees don't have `.env`, which is gitignored. Source it by absolute path: `set -a; . /workspaces/qte77/feelings/.env; set +a`.
- **Run output must survive the worktree being cleaned up.** Write run files to the shared folder `/workspaces/qte77/feelings-runs/`, which is outside every repo, never to `eval/` in the worktree. Existing baseline runs are in the main checkout's `eval/run-*.jsonl`; read them from there.
- Sibling repos are reached by absolute path, because relative `../` paths break inside a worktree:
  - `/workspaces/qte77/polyfetch-scrape` (page check);
  - `/workspaces/qte77/yt-dlp` (read-only; the fixtures come from `c7fb478d2`; never modify it).
- After an environment reset: `uv run --directory /workspaces/qte77/polyfetch-scrape patchright install chromium --only-shell`.
- **Memory:** this Codespace has about 8 GB and no swap, shared with VS Code and other Claude sessions. On 2026-09-29, Chromium segfaulted on the page check's full-page screenshot with about 1 GB available. So run **at most one page check at a time**, and check `free -m` first. Parallel lanes that only run Python are fine.
- The `pre-push` hook (`core.hooksPath=.githooks`, shared by all worktrees) runs the local Jev check. It never blocks. In a worktree it prints "skipped" because there's no `.env`; that's expected.
- BAML needs `. ~/.baml/env` and `BAML_AGENT_SKILL_CHECK=off`.
- Don't retune the 0.70 setting on data that's also reported (see E1).

## Lanes and worktrees

Lanes run in parallel only when they **own different files**. The main session owns the shared files and edits them only between merges.

| Lane | Rows | Owns (may edit) | Must not edit |
|---|---|---|---|
| A · metrics | P4 | `eval/metrics.py`, `eval/test_metrics.py` | site/, fixtures, other eval files |
| B · rerun | P1 | nothing in git: writes `/workspaces/qte77/feelings-runs/p1-*.jsonl` and a short report in its PR body | everything |
| C · cues from fixture building | P2 | `eval/fixtures_build.py`, `eval/test_fixtures_build.py`, a new `eval/fixtures-p2-*.jsonl` (add a `.gitignore` exception) | `eval/fixtures.jsonl`, `eval/fixtures-ytdlp.jsonl` |
| D · label queue | P3 | a new `eval/review_queue.py` and its test, a new `docs/reviews/2026-09-29-label-queue.md` | the fixture files (owner decides relabels) |
| E · local check | E4 | `eval/jev_check.py`, `eval/test_jev_check.py`, `.githooks/pre-push` | everything else |
| F · page | Pub1 (phase 4) | `site/**`, `scripts/check_site.py` | eval/; **serial only**, one page lane at a time |
| G · one command | R1 | a new `Makefile` (or `scripts/eval.sh`), `export()` provenance in `eval/metrics.py` **after lane A merges** | site/ |

**Shared files (main session only):**
- the "Start here" block of this plan;
- `README.md` (new commands, env vars, URLs);
- `.gitignore`;
- `site/data/*.json`, re-exported after the metric lanes merge.

**Conflicts:**
- Each lane's single row line in this plan may still conflict with a neighbouring row. The main session resolves that when rebasing, before merging.
- If two lanes need the same file, run them one after the other and note it in the table.

**Ports for the page check:** lane F uses 8137. Any other lane that needs a page preview uses 8140 plus its lane letter's index.

**The full gate, every lane, before pushing:**
- `uvx ruff check eval/ scripts/ && uvx ruff format --check eval/ scripts/`
- `uv run --no-project --with pytest --with typesafe-sdk pytest eval/ -q --rootdir eval`
- `shellcheck .githooks/pre-push`, if touched.
- For page changes: `uv run --directory /workspaces/qte77/polyfetch-scrape python <worktree>/scripts/check_site.py <out_dir> http://localhost:<port>/`, with the site served from the worktree.

## Pre-registered bars (set before any rerun; don't move them afterwards)

| Change | Ships only if |
|---|---|
| Any change to questions, settings or fixtures | ROC-AUC ≥ 0.85 per question, with the 95% interval's lower bound ≥ 0.80, **on both** the 184 set and the yt-dlp set |
| A per-repo setting (E1) | Wrongly flags ≤ 5% **on the half not used to choose it** |
| Reproducibility (P1) | Each question's ROC-AUC within ±0.02 of `v0.8.0`, and the wrongly-flags count within ±1 fixture |
| Cues from fixture building (P2) | If ROC-AUC on the realistic-header set drops by more than 0.05 on any question, the published numbers are overstated. Then update the page's caveat and re-run the affected numbers before any enhancement |

> **Amendment, 2026-09-29 (before any enhancement was measured):** P5's fixture change
> *corrects a measurement cue*, so it is adopted **whichever way the numbers move**. The
> "any change … ≥ 0.85" bar applies to enhancements measured **on the corrected fixtures**,
> not to the correction itself. After P5, *unused abstraction* is 0.838 (0.827 without the 16
> residual new-file records). That fails this plan's 0.85 bar, but it still passes 0001's
> post-AUC ≥ 0.80, and the page's rating drops from "good" to "fair". This is reported as a
> finding, not a failure to fix.

## Code, file and source map

The full map of everything built in 0001 is in [0001 → Source map](2026-09-23-0001-jev-coding-gate-pilot.md#source-map); read it for anything not listed here. The entries below are what this arc touches, with line references at `5777127`.

| What | Where (line) | Role in 0002 |
|---|---|---|
| Questions | `eval/concerns.py:6` `CONCERNS`, `:14` `state_for` | E2 adds variants next to them, keeping the originals for comparison. `test_jev_gate.py::test_questions_match_the_baml_version_exactly` forces `baml_src/code_gate.baml` to match |
| Jev runner | `eval/jev_gate.py:24` `check`, `:37` `run`, `:61` `main` (`uv run eval/jev_gate.py [k] < fixtures > run.jsonl`) | P1 reruns it; E2 needs a questions argument |
| Claude runner | `eval/claude_gate.py:93` `run`, `:113` `main` (`[k] [model] [workers]`) | Reruns are owner-gated (spend) |
| Metrics (after #37) | `eval/metrics.py:32` `auc`, `:41` `average_precision`, `:98` `summarize` (now also `auc_pre_ci`, `pr_auc_pre`, `brier_pre`, and `pre.false_reject_rate_ci` / `catch_rate_ci`, from a bootstrap with seed 0 and 1,000 resamples), `:192` `sweep`, `:228` `export`, `:260` `main` | R1 adds provenance to `export` |
| Fixture builder (after #40) | `eval/fixtures_build.py:101` `_append_hunk` (**writes the fake `@@ -500,0 +501,N @@` headers**), `:111` `_new_file` (**new-file sections, marked `index 0000000..0000000`**), `:208` `add_unused_abstraction`, `:355` `add_scope_creep`, `:280` `realistic_headers`, `:320` `inline_new_files`, `:526` `VARIANTS`, `:529` `build_variant`, `:497` `build`, `:549` `main` (`--variant headers\|inline`) | P5 makes `add_unused_abstraction` and `add_scope_creep` place code in an existing file, reusing `inline_new_files` and `realistic_headers` |
| Label review list (after #38) | `eval/review_queue.py:139` `parse_args`, `:164` `main`; output `docs/reviews/2026-09-29-label-queue.md` | Regenerate only for a new review round; relabels go in a separate PR |
| Cue variants | `eval/fixtures-p2-{headers,inline}{,-ytdlp}.jsonl`; run files in `/workspaces/qte77/feelings-runs/p2-*` | Evaluation only; provenance in `eval/fixtures.README.md` |
| Fixtures (settled by P5) | `eval/fixtures.jsonl` (184, sha256 `69859a31…`; before P5 `1d94ddac…`), `eval/fixtures-ytdlp.jsonl` (120, `e6f384d1…`; before P5 `990e2eaa…`); provenance in `eval/fixtures.README.md` | Don't edit in lanes. `site/data/*.json` still describe the pre-P5 versions until the Claude rerun |
| Baseline runs (local, gitignored) | main checkout `eval/run-{python,baml}-184.jsonl`, `run-claude-{haiku,claude-sonnet-5,claude-opus-5-5}-184.jsonl`, and the same names with `-ytdlp` | P1 compares against them; P3 builds its queue from them |
| Page data | `site/data/results.json` (5 setups on 184, generated 2026-09-25), `site/data/ytdlp.json` (5 setups on yt-dlp, 2026-09-29), `site/data/pilot-2026-09-24.json` (frozen) | Main session re-exports after merges |
| Page | `site/index.html` sections `#answer`:45, `#questions`:57, `#compare`:67, `#external`:85, `#alternatives`:107, `#strictness`:138, `#method`:163; `site/app.js` `answer`:64, `ratings`:110, `compare`:143, `strictness`:188, `resultsTable`:224, `external`:370 | Pub1 (lane F) shows the intervals, per-repo settings and the P2 result |
| Page check | `scripts/check_site.py`: row counts, deep links, and terms that must not appear | Lane F extends it |
| Local check | `eval/jev_check.py:32` `review`, `:79` `main` (always exits 0); `.githooks/pre-push` | E4 |
| Deploy | `.github/workflows/gh-pages.yaml`: on push to `site/**`, plus `workflow_dispatch`, which writes `version.txt` | Redeploy after each release |
| Commands | [0001 → Commands](2026-09-23-0001-jev-coding-gate-pilot.md#commands) | Every existing command, with exact arguments |

## Remaining work

EXACTLY ONE table. Gate: `agent` / `owner` / `data`. Phases run in order; the rows inside a phase run in parallel lanes.

| # | Phase · lane | Item | Gate | Done when |
|---|---|---|---|---|
| P1 | 1 · B | **Is it reproducible?** Rerun both Jev runners (k=5) on the 184 and yt-dlp sets with the pinned `jev-1.13.0`. Compare each question's ROC-AUC, agreement and wrongly-flags count with the baseline runs. About $0.30. | agent | **Done, PR #39.** Mostly reproducible: all 16 per-question AUCs (4 questions × 4 runner/set combos) within ±0.02 of baseline. Wrongly-flags count held on 3/4 combos (python-184 1→1, baml-184 1→1, baml-ytdlp 7→7) but **failed the ±1 bar on python-ytdlp (9→7, Δ2)** — two borderline fixtures (`good-111`, `good-112`) flipped right at the 0.70 threshold (0.74→0.69, 0.70→0.68), sampling noise not drift. No cache (≤2.6% identical answers), no errors, cost $0.15 (python only; BAML untracked). |
| P2 | 1 · C | **Is Jev reading cues from how the fixtures were built?** Two variants of the existing flawed records: (a) replace the fake `@@ -500,0 +501,N @@` headers with realistic ones, continuing after the section's last real hunk; (b) move the `new file mode` scope-creep and unused-abstraction additions into an existing source file. Rerun Jev on each variant (k=5) and compare with the baseline, clean records unchanged. The helpers are test-first. | agent | **Done (PR qte77/feelings#40):** `inline` drops single_use_abstraction AUC by 0.054 (184 set) / 0.053 (yt-dlp set) — bar exceeded on both, ~14× the P1 noise floor, a lower bound (16/50 cue-carrying records had no target file to move into). `headers` stays within noise on both sets. Builder follow-up recommended (route `add_unused_abstraction` through `_append_hunk`), not done in this PR |
| P3 | 1 · D | **Are the labels right?** *Queue done in [#38](https://github.com/qte77/feelings/pull/38); owner review pending.* `eval/review_queue.py` lists the records where every setup (5 on the 184, 5 on yt-dlp) disagrees with the label at 0.70, plus yt-dlp #119, #120 and #126. It writes `docs/reviews/2026-09-29-label-queue.md` with the id, message, a short diff excerpt, each setup's score and a blank "owner verdict" column. | agent (queue), then **owner** (about 1 h review) | The queue is merged. After the owner's verdicts, relabels are applied in a separate PR with a reason each, and noted in `eval/fixtures.README.md` |
| P4 | 1 · A | **How noisy are the numbers?** Test-first in `summarize`: a bootstrap 95% interval for per-question ROC-AUC and for the wrongly-flags rate (fixed seed, 1,000 resamples); PR-AUC; the Brier score. (This absorbs 0001 row 23.) **Done: PR [#37](https://github.com/qte77/feelings/pull/37).** | agent | Tests first; new fields in `export()` output; `results.json` and `ytdlp.json` re-exported by the main session |
| P5 | 1 · C | ***Done in #45 (2026-10-07); see "Start here".*** Remove the new-file cue P2 found: `settle()` in every build; both sets settled in place; Jev and Claude (changed records only) rerun; page re-exported. | done | Done: fixtures committed with provenance; page numbers replaced; the caveat is now "Examples fixed" |
| E1 | 2 | **A setting per repo, without tuning on reported numbers.** Split each set in half, stratified by label and source commit. Choose the lowest setting with wrongly flags ≤ 5% on one half; report the other half. | agent | Per-repo settings and held-out results against the pre-registered bar |
| E2 | 2 | **Question variants:** alternative wordings of each question; one *score* question ("how risky, 0–4"); one *choice* question ("which flaw, if any"). The runner takes a questions file. | agent | Each variant scored on both sets with intervals; adopted only if it meets the bar on both |
| E3 | 2 | **Real flaws, not only added ones:** collect about 20 real flawed commits (later reverted; fixes to skipped or weakened tests; review comments about duplication) from the owner's repos and yt-dlp's history, read-only. | **owner:** worth it? | A labelled `eval/fixtures-real.jsonl` with provenance, scored |
| E4 | 2 · E | **Local check:** judge each commit separately, and don't flag diffs where weakened-assert lines are only test data (the one false alarm, `8afa0c4`). Test-first. | agent | Tests plus a replay of the last 20 commits with no false alarm there |
| E5 | 2 | **Other models on the same harness:** Laya (issue #24; the route chosen in 0001 row 22 is a manual GitHub Actions batch) and kev (jaredpalmer/kev, open weights; check its licence first-hand) | agent (Laya); owner for any spend or hosting | Their runs exported next to Jev; the page's alternatives section updated from measured numbers |
| R1 | 3 · G | **One command:** `make eval` runs the fixture checks, both Jev runners, the export with intervals and the page check. Claude only with `CLAUDE=1`. `export()` records the model id, fixture sha256, git sha and date. | agent | One command reproduces `results.json` and `ytdlp.json`; the provenance is shown in the page footer or method |
| Pub1 | 4 · F | **Publish:** the page shows the intervals, the per-repo settings and the P2 outcome, whichever way it came out. Update `check_site.py`. | agent | Release, live page check, "Start here" updated |
| 12 | carried | Upstream PR to BoundaryML/feelings (0001 row 12). Waiting on their reply to #2 and #1 (none as of 2026-09-29). Branch `contrib/code-review-example` is the PR head. | owner / their reply | The PR opened or dropped per their answer; the branch deleted |
| 16 | carried | Jev across the owner's other repos (0001 row 16) | owner, after a trial (18) | Per 0001 |
| 17 | carried | Finish the `coding-harness-eval` rename references in 4 repos (0001 row 17) | owner | Per 0001 |
| 9 | carried | Runners for Codex, Gemini CLI, opencode and HarnessRouter (0001 row 9). **Reframed by [#43](https://github.com/qte77/feelings/issues/43), 2026-10-07:** the Claude baseline was a single-turn, tool-less `claude -p` call with our own system prompt, not the Claude Code agent harness. So the multi-harness finding (harness moves agent scores) mostly doesn't apply to judging. Run each runner the same way (tools off, same system prompt, one turn) and record harness and version per row. HarnessRouter's API is now `POST /v1/responses` with `metadata.harness_id` (see qte77/coding-harness-eval#58) | agent; owner for logins | Per 0001, plus #43 |
| 18 | carried | Go or no-go on a real trial (0001 row 18); on hold. The local check (row 24) is the first vehicle | owner | Per 0001 |
| 19 | carried | Example browser on the page (0001 row 19). **It edits site/, so it can't run in parallel with Pub1** | agent | Per 0001 |
| 20 | carried | Suspected deep-link bug in analyze-stock-kpi (0001 row 20) | agent; owner approves any issue | Per 0001 |
| 24 | carried | Is the local check useful? Label about 30 pushes (0001 row 24) | data, then owner | Per 0001 |
| 28 | carried | yt-dlp canary: tracked in qte77/yt-dlp#1–#5 (0001 row 28); nothing to do here | the fork's issues | Close when qte77/yt-dlp#1 closes |
