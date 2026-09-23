# fixtures.jsonl
Labelled diffs for evaluating Jev (`scope_creep`, `single_use_abstraction`,
`duplication`, `weakened_tests`).

**Source**: `analyze-stock-kpi` (github.com/qte77/analyze-stock-kpi). Verified
public: GitHub page shows "Public" badge (WebFetch); local `LICENSE` =
Apache-2.0. (`gh repo view` failed on 401 — no `gh` auth, not a visibility
signal.) Clone was shallow (depth 50); `git fetch --unshallow` succeeded
mid-run, giving full history (283 commits, no merges — repo squash-merges).
**Selection**: 30 real, non-merge, `src/`/`tests/` `.py`-touching commits,
skipping formatting/dep-bump/changelog-only/mechanical-rename commits and
any whose real diff already showed one of the four problems (one found:
"remove four trivial tests" — excluded, not mislabelled). Deviation: only
21/55 fit 400-12000 chars on raw `git show` (bulk is CHANGELOG/docs/workflow
noise); `diff` uses `git show --format= --patch <sha> -- src tests`
(path-filtered) instead — 40 candidates, 30 kept for spread across history.

**Mutations** (built from real diff text): `scope_creep`/
`single_use_abstraction` (8 each) append a new file (unrelated feature /
single-use class). `duplication` (7) appends a near-copy of a function
already added in the same diff. `weakened_tests` (7) deletes the first added
`assert` line (one exception inserts `@pytest.mark.skip`). Appended hunks use
synthetic `@@ -500,0 +501,N @@` headers (valid syntax, not `git apply`-safe).
**Attribution**: diffs are excerpts of qte77/analyze-stock-kpi, licensed
Apache-2.0 (see that repo's `LICENSE` and `NOTICE`); `bad-*` records are
modified versions.
**Leak scrub** (2026-09-23): 10 bad records named or described their own
problem (`Near-duplicate of …` docstrings, `_repeat`/`_again`/`_secondary`/
`Copy` names, "kept for documentation purposes"). Reworded neutrally, code
unchanged, so Jev must judge the code, not read the label.
**weakened_tests fix** (2026-09-23): 6 of 7 originally dropped an added `+ assert` line,
which leaves no trace in a diff, so they were unjudgeable (every model scored 0.56–0.84 AUC
on them). Each now shows the weakening: `- assert A == B` / `+ assert A`, with the hunk's old
count bumped. bad-08 (`@pytest.mark.skip`) was already visible.
**Limits**: "good" labels are manual spot-review, not a formal audit;
mutations are synthetic, not real author commits. `scope_creep` and
`single_use_abstraction` share one surface shape (a new appended file), so
per-concern AUC also tests whether Jev tells them apart. Some
`single_use_abstraction` objects are defined but never used.
