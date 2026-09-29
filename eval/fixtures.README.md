# fixtures.jsonl
Labelled diffs for evaluating Jev (`scope_creep`, `single_use_abstraction`,
`duplication`, `weakened_tests`).
**Terms**: the results page calls the two groups **clean** (`good-*` records: a real commit,
unchanged) and **flawed** (`bad-*` records: one issue a code reviewer should catch, mostly
added to a real commit on purpose). Here and in the code they stay `good` / `bad`, because
the record ids, run files and `results.json` keys (`n_good`, `n_bad`) use those names.

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
**Good-label audit (2026-09-25)**: every good record was checked for added non-test
classes or functions that nothing else in its diff mentions. The rule was applied to all
61, whatever any model scored. Six matched; four are used by a framework (a file-like
`read()`, `autouse` pytest fixtures, `@app.command()` CLI functions) and stay good. Two
real commits genuinely add an abstraction nothing uses (Agents-eval `812f145`:
`DummyTool`, `use_tool`; doc-pipeline-engine `ee01aed`: `AdapterBase`). All records from
those two sources now carry `single_use_abstraction: true`, and their real-diff records
are renamed `bad-NN-single_use_abstraction-real-<sha>`.
Totals: 59 good, and 30 / 37 / 30 / 32 bad for weakened_tests / single_use_abstraction
/ duplication / scope_creep.
**Held-out set `fixtures-ytdlp.jsonl` (2026-09-27, 120 records, ids 101–130)**: built by
`eval/fixtures_build.py /dev/null 30 101 ../yt-dlp=qte77/yt-dlp:yt_dlp,test` from the owner's
local fork of yt-dlp (head `c7fb478d2`), read only. yt-dlp is released under the Unlicense (public
domain, checked in its `LICENSE`); `bad-*` records are modified versions. yt-dlp's own
`.NO_AI` policy forbids AI-made issues, PRs and comments; this set involves no contact with yt-dlp.
It is kept apart from `fixtures.jsonl` and is never used to tune the 0.70 setting. What differs
from the other repos: code lives in `yt_dlp/`, unittest tests in `test/`, so `weaken_test`
also rewrites `self.assertEqual(A, B)` to `self.assertTrue(A)`; the clean filter
(`may_weaken_tests`) also skips diffs that call `pytest.skip`, add an extractor test's `'skip'`
or `'only_matching': True`, or remove more `_TESTS` URLs than they add. Spot check: all 30 good
subjects read, and the four suspicious diffs opened; one (`ade8c2b`, "Skip flaky tests")
really skipped tests via `pytest.skip(...)`, which led to that filter rule and a rebuild.
Totals: 30 good, and 19 / 26 / 19 / 26 bad for weakened_tests / single_use_abstraction /
duplication / scope_creep.
**Cue variants `fixtures-p2-*.jsonl` (2026-09-29, plan 0002 row P2, #40)**: derived from
`fixtures.jsonl` and `fixtures-ytdlp.jsonl` with `uv run eval/fixtures_build.py --variant
headers|inline <fixtures.jsonl>`. Only `bad-*` records are transformed; clean records are copied
unchanged, and ids and labels stay the same.
- `headers` rewrites the synthetic `@@ -500,0 +501,N @@` header to continue after the section's
  last real hunk: 43 changed on the 184 set, 30 on yt-dlp.
- `inline` moves a builder-added new-file section, recognised by its `index 0000000..0000000`
  line, into an existing non-test source file of the same diff. 34 changed on the 184 set, and
  16 couldn't be moved because the diff has no other source file; 41 changed on yt-dlp.
- Result: with `inline`, *unused abstraction* first-answer ROC-AUC falls from 0.894 to 0.860
  (184) and from 0.851 to 0.799 (yt-dlp). So the new-file shape is a cue, and plan 0002 row P5
  fixes the builder.
- These files are **evaluation variants, not replacements**; the canonical sets stay
  `fixtures.jsonl` and `fixtures-ytdlp.jsonl` until P5.
**Limits**: "good" labels are manual spot-review for the original 60 and filter-based for the extension, not a formal audit;
mutations are synthetic, not real author commits. `scope_creep` and
`single_use_abstraction` share one surface shape (a new appended file), so
per-concern AUC also tests whether Jev tells them apart. Some
`single_use_abstraction` objects are defined but never used.
