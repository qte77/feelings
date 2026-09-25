# fixtures.jsonl
Labelled diffs for evaluating Jev (`scope_creep`, `single_use_abstraction`,
`duplication`, `weakened_tests`).

**Source (original 60, ids 01–30)**: `analyze-stock-kpi` (github.com/qte77/analyze-stock-kpi). Verified
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
**Attribution**: diffs are excerpts of the repo named in each record's
`source_repo` (qte77/analyze-stock-kpi, qte77/polyfetch-scrape,
qte77/doc-pipeline-engine, qte77/Agents-eval), all licensed Apache-2.0 (see each
repo's `LICENSE`); `bad-*` records are modified versions.
**Leak scrub** (2026-09-23): 10 bad records named or described their own
problem (`Near-duplicate of …` docstrings, `_repeat`/`_again`/`_secondary`/
`Copy` names, "kept for documentation purposes"). Reworded neutrally, code
unchanged, so Jev must judge the code, not read the label.
**weakened_tests fix** (2026-09-23): 6 of 7 originally dropped an added `+ assert` line,
which leaves no trace in a diff, so they were unjudgeable (every model scored 0.56–0.84 AUC
on them). Each now shows the weakening: `- assert A == B` / `+ assert A`, with the hunk's old
count bumped. bad-08 (`@pytest.mark.skip`) was already visible.
**single_use_abstraction shape** (checked 2026-09-25, all 8): a new private class
instantiated exactly once on a module-level line of its own new file, whose result nothing
else in the diff uses. That fits both the old question ("used only once") and the
reworded one ("nothing else in the diff uses"); new fixtures keep this shape.
**Extension (2026-09-25, 124 records, ids 31–61)**: built by
`eval/fixtures_build.py` (one good plus three bad per source commit; commits used by
the original 60 are skipped; each source serves the scarcest concern first). Sources are
all public and Apache-2.0, checked with `gh api repos/qte77/<repo>` on 2026-09-25:
qte77/polyfetch-scrape (23 commits), qte77/doc-pipeline-engine (7) and
qte77/Agents-eval (1). Every record carries `source_repo` and `source_sha`; `bad-*`
records are modified versions.
The builder's rules for the new records:
- Mutations: the `weakened_tests` rewrite only when the removed right side is truthy
  and the `==` is top-level; `duplication` copies an added function whole, including a
  multi-line signature; `scope_creep` alternates between inside an existing file and a
  new file.
- Checks on every bad record: consistent hunk counts, no leak words in the lines the
  mutation adds, and the inserted code parses.
- The good records' real diffs come from filters (size 400–12000 chars, skip dep, docs
  and format commits, skip diffs that already remove asserts or add `pytest.mark.skip`),
  **not a manual review**.
Totals: 61 good, and 30 / 31 / 30 / 32 bad for weakened_tests / single_use_abstraction
/ duplication / scope_creep.
**Limits**: "good" labels are manual spot-review for the original 60 and filter-based for the extension, not a formal audit;
mutations are synthetic, not real author commits. `scope_creep` and
`single_use_abstraction` share one surface shape (a new appended file), so
per-concern AUC also tests whether Jev tells them apart. Some
`single_use_abstraction` objects are defined but never used.
