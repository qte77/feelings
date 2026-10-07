# Label review queue (2026-09-29)

> **Note (P5, 2026-09-29):** this queue was built on the v0.9.0 fixtures. P5 later rewrote how
> the flaws are *placed* in 148 flawed diffs (no labels changed), so the review itself is still
> valid. The diff excerpts and scores below show the earlier versions.

**Purpose:** plan [0002](../plans/2026-09-29-0002-check-hardening.md) row P3 — "are the labels right?" This
queue lists the fixtures where every setup that answered agrees with each other but disagrees with the
label, on the first answer (sample 0) at the 0.70 setting: a **clean** record every setup flags (some
concern scored ≥ 0.70), or a **flawed** record whose labelled concern every setup misses (scored < 0.70).
It also includes three explicitly requested borderline ids from the yt-dlp set (`good-119-6a763a5`,
`good-120-35da8df`, `good-126-c014fbc`), marked "requested via `--also`" — some of those did not meet the
"every setup" bar on their own; they're here because they were close.

Built by [`eval/review_queue.py`](../../eval/review_queue.py) (tests in `eval/test_review_queue.py`) from
the baseline runs recorded locally in `eval/run-*.jsonl` (gitignored, main checkout only — see the plan's
[source map](../plans/2026-09-29-0002-check-hardening.md#code-file-and-source-map)):

| Set | Fixtures | Runs (name — generated) |
|---|---|---|
| 184 | `eval/fixtures.jsonl` | Jev, without BAML — 2026-09-25 · Jev, with BAML — 2026-09-25 · Claude Haiku 4.5 — 2026-09-25 · Claude Sonnet 5 — 2026-09-25 · Claude Opus 5.5 — 2026-09-25 |
| yt-dlp | `eval/fixtures-ytdlp.jsonl` | Jev, without BAML — 2026-09-27 · Jev, with BAML — 2026-09-27 · Claude Haiku 4.5 — 2026-09-29 · Claude Sonnet 5 — 2026-09-29 · Claude Opus 5.5 — 2026-09-29 |

**How to fill this in:** for each record, write one line after **Owner verdict** — `keep` (the label is
right), `relabel to …` (name the correct label), or `drop` (the fixture shouldn't be scored at all) —
with a short reason either way. The diff excerpt is only the first ~15 added lines from the *start* of
the diff; for `bad-*` records the mutation is often appended near the end (see
`eval/fixtures.README.md`), so the excerpt may not show the flaw itself — read the full record by id in
`eval/fixtures.jsonl` or `eval/fixtures-ytdlp.jsonl` before deciding.

**What happens next:** this lane (P3) only builds and merges the queue. Once the owner's verdicts are in,
relabels are applied in a **separate PR**, one reason per change, noted in `eval/fixtures.README.md`. This
file is not regenerated in place after that — treat it as a record of the review, not a live report.

---

## 184 set

### Flawed, missed by every setup (2)

#### `bad-30-duplication-195d16f`

- **source**: `qte77/analyze-stock-kpi`@`195d16f`
- **message**: feat(aggregator): split into best + worst paired universes (#199)
- **label**: duplication — questioned: duplication
- **scores** (max concern, first answer):
  - Jev, without BAML: `duplication` 0.23
  - Jev, with BAML: `duplication` 0.23
  - Claude Haiku 4.5: `duplication` 0.10
  - Claude Sonnet 5: `duplication` 0.55
  - Claude Opus 5.5: `duplication` 0.55

```diff
+) -> tuple[list[str], list[str], list[AuditRow]]:
+    """Build the aggregated-scores best + worst preset pair + per-ticker audit.
+        top_n: Each side of the ranking (default 25). Output is two
+            lists, each up to ``top_n``.
+        ``(best_tickers, worst_tickers, audit_rows)``. ``best_tickers``
+        is the top-``top_n`` by composite-mean; ``worst_tickers`` is the
+        bottom-``top_n``. Both sorted ASCII ascending. Disjoint sets.
+        ``audit_rows`` has one entry per ticker encountered (including
+        excluded ones); rank is ``+1..+top_n`` for best, ``-top_n..-1``
+        for worst, ``None`` for excluded.
+        return [], [], []
+    best_tickers: list[str] = []
+    worst_tickers: list[str] = []
+        best_tickers.append(ticker)
+        worst_tickers.append(ticker)
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

#### `bad-33-weakened_tests-dfbba22`

- **source**: `qte77/polyfetch-scrape`@`dfbba22`
- **message**: test(e2e): guard emulation/video + remove unposted show-hn draft (#174)
- **label**: weakened_tests — questioned: weakened_tests
- **scores** (max concern, first answer):
  - Jev, without BAML: `weakened_tests` 0.48
  - Jev, with BAML: `weakened_tests` 0.49
  - Claude Haiku 4.5: `weakened_tests` 0.30
  - Claude Sonnet 5: `weakened_tests` 0.15
  - Claude Opus 5.5: `weakened_tests` 0.60

```diff
+def test_patchright_emulation_and_video_record_real_webm(tmp_path) -> None:
+    """Emulation (device/color_scheme) + video recording (#162) produce a real .webm.
+
+    Guards the new context-time RenderOptions end-to-end against a real browser:
+    the recording is finalized on context close and its path surfaces on Response.
+    """
+    resp = fetch(
+        "https://quotes.toscrape.com/js/",
+        tier="patchright",
+        render=RenderOptions(
+            wait_until="networkidle",
+            device="iPhone 13",
+            color_scheme="dark",
+            record_video_dir=str(tmp_path),
+        ),
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

### Clean, flagged by every setup (0)

## yt-dlp set

### Flawed, missed by every setup (3)

#### `bad-112-weakened_tests-7bd79d9`

- **source**: `qte77/yt-dlp`@`7bd79d9`
- **message**: [ie/youtube] Allow `ejs` patch version to differ (#15263)
- **label**: weakened_tests — questioned: weakened_tests
- **scores** (max concern, first answer):
  - Jev, without BAML: `scope_creep` 0.70
  - Jev, with BAML: `scope_creep` 0.71
  - Claude Haiku 4.5: `scope_creep` 0.70
  - Claude Sonnet 5: `weakened_tests` 0.30
  - Claude Opus 5.5: `weakened_tests` 0.60

```diff
+        self.assertTrue(version_tuple('invalid', lenient=True))
+        self.assertEqual(version_tuple('1.2.3', lenient=True), (1, 2, 3))
+        self.assertEqual(version_tuple('12.34-something', lenient=True), (12, 34, -1))
+from yt_dlp.utils import version_tuple
+                # Matching patch version is expected to have same hash
+                if version_tuple(script.version, lenient=True)[:2] != version_tuple(self._SCRIPT_VERSION, lenient=True)[:2]:
+from ._utils import _get_exe_version_output, detect_exe_version, version_tuple
+        vt = version_tuple(version, lenient=True)
+        vt = version_tuple(version, lenient=True)
+        vt = version_tuple(version, lenient=True)
+        vt = version_tuple(version, lenient=True)
+def version_tuple(v, *, lenient=False):
+    parse = int_or_none(default=-1) if lenient else int
+    return tuple(parse(e) for e in re.split(r'[-.]', v))
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

#### `bad-126-duplication-c014fbc`

- **source**: `qte77/yt-dlp`@`c014fbc`
- **message**: [utils] `subs_list_to_dict`: Add `lang` default parameter (#11508)
- **label**: duplication — questioned: duplication
- **scores** (max concern, first answer):
  - Jev, without BAML: `scope_creep` 0.86
  - Jev, with BAML: `scope_creep` 0.85
  - Claude Haiku 4.5: `scope_creep` 0.35
  - Claude Sonnet 5: `single_use_abstraction` 0.85
  - Claude Opus 5.5: `single_use_abstraction` 0.85

```diff
+        }, all, {subs_list_to_dict(lang=None)}]) == {
+        assert traverse_obj([
+            {'name': 'de', 'url': 'https://example.com/subs/de.ass'},
+            {'name': 'de'},
+            {'name': 'en', 'content': 'content'},
+            {'url': 'https://example.com/subs/en'},
+        ], [..., {
+            'id': 'name',
+            'url': 'url',
+            'data': 'content',
+        }, all, {subs_list_to_dict(lang='en')}]) == {
+            'de': [{'url': 'https://example.com/subs/de.ass'}],
+            'en': [
+                {'data': 'content'},
+                {'url': 'https://example.com/subs/en'},
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

#### `bad-128-duplication-b103aca`

- **source**: `qte77/yt-dlp`@`b103aca`
- **message**: [utils] Fix and improve `find_element` and `find_elements` (#11443)
- **label**: duplication — questioned: duplication
- **scores** (max concern, first answer):
  - Jev, without BAML: `single_use_abstraction` 0.86
  - Jev, with BAML: `single_use_abstraction` 0.85
  - Claude Haiku 4.5: `scope_creep` 0.35
  - Claude Sonnet 5: `single_use_abstraction` 0.75
  - Claude Opus 5.5: `single_use_abstraction` 0.90

```diff
+    find_element,
+    find_elements,
+_TEST_HTML = '''<html><body>
+    <div class="a">1</div>
+    <div class="a" id="x" custom="z">2</div>
+    <div class="b" data-id="y" custom="z">3</div>
+    <p class="a">4</p>
+    <p id="d" custom="e">5</p>
+</body></html>'''
+
+    def test_find_element(self):
+        for improper_kwargs in [
+            dict(attr='data-id'),
+            dict(value='y'),
+            dict(attr='data-id', value='y', cls='a'),
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

### Clean, flagged by every setup (3)

#### `good-119-6a763a5`

- **source**: `qte77/yt-dlp`@`6a763a5`
- **message**: [compat] Add `compat_datetime_from_timestamp` (#11902)
- **label**: clean
- **why here**: requested via `--also`, not auto-selected at the 0.70 setting
- **scores** (max concern, first answer):
  - Jev, without BAML: `scope_creep` 0.77
  - Jev, with BAML: `scope_creep` 0.77
  - Claude Haiku 4.5: `scope_creep` 0.20
  - Claude Sonnet 5: `scope_creep` 0.20
  - Claude Opus 5.5: `scope_creep` 0.72

```diff
+import datetime as dt
+from yt_dlp.compat import compat_etree_fromstring, compat_expanduser, compat_datetime_from_timestamp
+    def test_compat_datetime_from_timestamp(self):
+        self.assertEqual(
+            compat_datetime_from_timestamp(0),
+            dt.datetime(1970, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc))
+        self.assertEqual(
+            compat_datetime_from_timestamp(1),
+            dt.datetime(1970, 1, 1, 0, 0, 1, tzinfo=dt.timezone.utc))
+        self.assertEqual(
+            compat_datetime_from_timestamp(3600),
+            dt.datetime(1970, 1, 1, 1, 0, 0, tzinfo=dt.timezone.utc))
+
+        self.assertEqual(
+            compat_datetime_from_timestamp(-1),
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

#### `good-120-35da8df`

- **source**: `qte77/yt-dlp`@`35da8df`
- **message**: [utils] Add improved `jwt_encode` function  (#14071)
- **label**: clean
- **why here**: requested via `--also`, not auto-selected at the 0.70 setting
- **scores** (max concern, first answer):
  - Jev, without BAML: `duplication` 0.85
  - Jev, with BAML: `duplication` 0.85
  - Claude Haiku 4.5: `duplication` 0.75
  - Claude Sonnet 5: `duplication` 0.50
  - Claude Opus 5.5: `duplication` 0.50

```diff
+    jwt_decode_hs256,
+    jwt_encode,
+    _JWT_KEY = '12345678'
+    _JWT_HEADERS_1 = {'a': 'b'}
+    _JWT_HEADERS_2 = {'typ': 'JWT', 'alg': 'HS256'}
+    _JWT_HEADERS_3 = {'typ': 'JWT', 'alg': 'RS256'}
+    _JWT_HEADERS_4 = {'c': 'd', 'alg': 'ES256'}
+    _JWT_DECODED = {
+        'foo': 'bar',
+        'qux': 'baz',
+    }
+    _JWT_SIMPLE = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmb28iOiJiYXIiLCJxdXgiOiJiYXoifQ.fKojvTWqnjNTbsdoDTmYNc4tgYAG3h_SWRzM77iLH0U'
+    _JWT_WITH_EXTRA_HEADERS = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImEiOiJiIn0.eyJmb28iOiJiYXIiLCJxdXgiOiJiYXoifQ.Ia91-B77yasfYM7jsB6iVKLew-3rO6ITjNmjWUVXCvQ'
+    _JWT_WITH_REORDERED_HEADERS = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmb28iOiJiYXIiLCJxdXgiOiJiYXoifQ.slg-7COta5VOfB36p3tqV4MGPV6TTA_ouGnD48UEVq4'
+    _JWT_WITH_REORDERED_HEADERS_AND_RS256_ALG = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJmb28iOiJiYXIiLCJxdXgiOiJiYXoifQ.XWp496oVgQnoits0OOocutdjxoaQwn4GUWWxUsKENPM'
```

**Owner verdict** (keep / relabel to … / drop, with reason): 

#### `good-126-c014fbc`

- **source**: `qte77/yt-dlp`@`c014fbc`
- **message**: [utils] `subs_list_to_dict`: Add `lang` default parameter (#11508)
- **label**: clean
- **why here**: requested via `--also`, not auto-selected at the 0.70 setting
- **scores** (max concern, first answer):
  - Jev, without BAML: `scope_creep` 0.78
  - Jev, with BAML: `scope_creep` 0.79
  - Claude Haiku 4.5: `scope_creep` 0.75
  - Claude Sonnet 5: `scope_creep` 0.40
  - Claude Opus 5.5: `scope_creep` 0.60

```diff
+        }, all, {subs_list_to_dict(lang=None)}]) == {
+        assert traverse_obj([
+            {'name': 'de', 'url': 'https://example.com/subs/de.ass'},
+            {'name': 'de'},
+            {'name': 'en', 'content': 'content'},
+            {'url': 'https://example.com/subs/en'},
+        ], [..., {
+            'id': 'name',
+            'url': 'url',
+            'data': 'content',
+        }, all, {subs_list_to_dict(lang='en')}]) == {
+            'de': [{'url': 'https://example.com/subs/de.ass'}],
+            'en': [
+                {'data': 'content'},
+                {'url': 'https://example.com/subs/en'},
```

**Owner verdict** (keep / relabel to … / drop, with reason): 
