import re

import pytest

from fixtures_build import (
    add_duplication,
    add_scope_creep,
    add_unused_abstraction,
    added_by,
    leaks,
    may_weaken_tests,
    parse_repo,
    parses,
    select,
    weaken_test,
)

SRC_DIFF = """diff --git a/src/pkg/fetch.py b/src/pkg/fetch.py
index 1111111..2222222 100644
--- a/src/pkg/fetch.py
+++ b/src/pkg/fetch.py
@@ -10,3 +10,9 @@ import time

 def get(url):
     return _session().get(url)
+
+
+def get_json(url, timeout=10):
+    response = get(url)
+    response.raise_for_status()
+    return response.json()
"""

TEST_DIFF = """diff --git a/tests/test_fetch.py b/tests/test_fetch.py
index 3333333..4444444 100644
--- a/tests/test_fetch.py
+++ b/tests/test_fetch.py
@@ -1,3 +1,6 @@
 from pkg.fetch import get_json


+def test_get_json_returns_payload(fake):
+    payload = get_json("http://x")
+    assert payload == {"ok": True}
"""


def hunk_counts_match(diff):
    """Every @@ header's line counts match the lines that follow it."""
    lines = diff.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@", line)
        if not m:
            continue
        old_n, new_n = int(m.group(1) or 1), int(m.group(2) or 1)
        body = []
        for nxt in lines[i + 1 :]:
            if nxt.startswith(("@@", "diff --git")):
                break
            body.append(nxt)
        old = sum(1 for b in body if not b.startswith("+"))
        new = sum(1 for b in body if not b.startswith("-"))
        if (old, new) != (old_n, new_n):
            return False
    return True


def test_fixture_diffs_have_consistent_hunk_counts():
    assert hunk_counts_match(SRC_DIFF)
    assert hunk_counts_match(TEST_DIFF)


def test_weaken_test_turns_an_added_equality_into_a_visible_weaker_assert():
    out = weaken_test(TEST_DIFF)
    assert '-    assert payload == {"ok": True}' in out
    assert "+    assert payload\n" in out
    assert '+    assert payload == {"ok": True}' not in out
    assert hunk_counts_match(out)  # the old count grows by the removed line


@pytest.mark.parametrize("falsy", ["0", "False", "None", '""', "[]", "{}", "0.0"])
def test_weaken_test_skips_falsy_right_sides_because_dropping_them_inverts_the_assert(falsy):
    # `assert code == 0` -> `assert code` would assert the opposite, not something weaker.
    diff = TEST_DIFF.replace('assert payload == {"ok": True}', f"assert payload == {falsy}")
    assert weaken_test(diff) is None


def test_weaken_test_skips_an_equality_nested_inside_brackets():
    # Cutting at a nested == would leave invalid code: `assert not any(f.get("url")`.
    diff = TEST_DIFF.replace('assert payload == {"ok": True}', 'assert not any(f.get("u") == "x" for f in payload)')
    assert weaken_test(diff) is None


def test_weaken_test_returns_none_without_an_added_equality_assert():
    assert weaken_test(SRC_DIFF) is None


def test_unused_abstraction_is_a_private_class_instantiated_once_and_never_used():
    out = add_unused_abstraction(SRC_DIFF, seed=0)
    new_file = out[out.rfind("diff --git") :]
    assert "new file mode 100644" in new_file
    cls = re.search(r"^\+class (_\w+)", new_file, re.MULTILINE).group(1)
    var = re.search(r"^\+(_\w+) = " + cls + r"\(", new_file, re.MULTILINE).group(1)
    code = "\n".join(line for line in new_file.splitlines() if line.startswith("+") and not line.startswith("+++"))
    assert code.count(cls) == 2  # defined once, instantiated once
    assert var not in out[: out.rfind("diff --git")]  # nothing else in the diff uses it
    assert code.count(var) == 1
    assert hunk_counts_match(out)


def test_duplication_near_copies_a_function_added_in_the_same_diff():
    out = add_duplication(SRC_DIFF, seed=0)
    added = out[len(SRC_DIFF) :]
    name = re.search(r"^\+def (\w+)\(", added, re.MULTILINE).group(1)
    assert name != "get_json" and name.startswith("get_json")
    assert "response.raise_for_status()" in added
    assert "diff --git a/src/pkg/fetch.py" not in added  # same file, extra hunk
    assert hunk_counts_match(out)


def test_duplication_copies_a_multiline_signature_whole():
    multi = SRC_DIFF.replace(
        "+def get_json(url, timeout=10):\n",
        "+def get_json(\n+    url, timeout=10\n+) -> dict:\n",
    ).replace("@@ -10,3 +10,9 @@", "@@ -10,3 +10,11 @@")
    assert hunk_counts_match(multi)
    added = add_duplication(multi, seed=0)[len(multi) :]
    code = "\n".join(line[1:] for line in added.splitlines() if line.startswith("+"))
    compile(code, "<dup>", "exec")  # raises SyntaxError if the signature was cut
    assert "return response.json()" in code


def test_duplication_returns_none_without_an_added_function():
    assert add_duplication(TEST_DIFF.replace("+def test_", "+x = 1  # "), seed=0) is None


@pytest.mark.parametrize("seed", [0, 1])
def test_scope_creep_adds_an_unrelated_function_in_an_existing_file_or_a_new_one(seed):
    out = add_scope_creep(SRC_DIFF, seed=seed)
    added = out[len(SRC_DIFF) :]
    assert re.search(r"^\+def \w+\(", added, re.MULTILINE)
    in_existing = "new file mode" not in added
    assert in_existing == (seed % 2 == 0)  # alternate the two shapes
    assert hunk_counts_match(out)


def test_leaks_flags_words_that_name_the_problem_only_in_added_lines():
    assert leaks("+    # near-duplicate of get_json\n") == ["duplicate"]
    assert leaks("+def get_json_copy(url):\n") == ["copy"]
    assert leaks("-    # unused helper\n") == []  # removed lines don't count
    assert leaks("+def get_json_for_report(url):\n") == []


def test_leak_check_ignores_the_authors_own_added_lines():
    # A real commit may say "copy" or "scope"; only text the mutation adds can leak the label.
    real = SRC_DIFF.replace("+    response = get(url)", "+    response = get(url)  # copy of scope rules")
    mutated = add_unused_abstraction(real, seed=0)
    assert leaks(mutated) != []  # a whole-diff scan would reject this record
    assert leaks(added_by(real, mutated)) == []


def test_added_by_returns_only_the_lines_a_mutation_added():
    out = weaken_test(TEST_DIFF)
    assert added_by(TEST_DIFF, out) == "+    assert payload\n"


def test_parses_accepts_valid_mutations_and_rejects_broken_ones():
    for mutate in (add_unused_abstraction, add_duplication, add_scope_creep):
        assert parses(SRC_DIFF, mutate(SRC_DIFF, 0))
    assert parses(TEST_DIFF, weaken_test(TEST_DIFF))
    broken = SRC_DIFF + "@@ -500,0 +501,2 @@\n+\n+def cut(\n"
    assert not parses(SRC_DIFF, broken)


def test_select_serves_the_scarcest_concern_first():
    all_four = dict.fromkeys(["scope_creep", "single_use_abstraction", "duplication", "weakened_tests"], "d")
    no_tests = {k: v for k, v in all_four.items() if k != "weakened_tests"}
    pool = [("newest", no_tests), ("older", all_four), ("too-few", {"duplication": "d"})]
    counts = {"scope_creep": 5, "single_use_abstraction": 5, "duplication": 5, "weakened_tests": 0}
    picked = select(pool, counts, n_sources=2)
    assert [source for source, _ in picked] == ["older", "newest"]  # "older" can serve weakened_tests
    assert "weakened_tests" in [c for c, _ in picked[0][1]]
    assert all(len(bad) == 3 for _, bad in picked)


def test_mutations_skip_names_the_real_diff_already_uses():
    # A template name that already appears in the diff could make "nothing else uses it" false.
    taken = SRC_DIFF + "+from pkg.config import RetryBudget, retry_budget, slugify, get_json_for_report\n"
    assert "RetryBudget" not in add_unused_abstraction(taken, seed=0)[len(taken) :]
    assert "def slugify(" not in add_scope_creep(taken, seed=0)[len(taken) :]
    assert "def get_json_for_report(" not in add_duplication(taken, seed=0)[len(taken) :]


@pytest.mark.parametrize("seed", range(6))
def test_no_mutation_leaks_its_own_label(seed):
    for out in (
        add_unused_abstraction(SRC_DIFF, seed),
        add_duplication(SRC_DIFF, seed),
        add_scope_creep(SRC_DIFF, seed),
        weaken_test(TEST_DIFF),
    ):
        assert leaks(out) == []


# ---- Other layouts (row 25: yt-dlp keeps code in yt_dlp/ and unittest tests in test/) ----

UNITTEST_DIFF = """diff --git a/test/test_utils.py b/test/test_utils.py
index 5555555..6666666 100644
--- a/test/test_utils.py
+++ b/test/test_utils.py
@@ -20,3 +20,6 @@ class TestUtil(unittest.TestCase):

     def test_existing(self):
         self.assertTrue(True)
+
+    def test_parse_codecs(self):
+        self.assertEqual(parse_codecs('avc1'), {'vcodec': 'avc1'})
"""

YTDLP_DIFF = (
    UNITTEST_DIFF
    + """diff --git a/yt_dlp/utils/_utils.py b/yt_dlp/utils/_utils.py
index 7777777..8888888 100644
--- a/yt_dlp/utils/_utils.py
+++ b/yt_dlp/utils/_utils.py
@@ -10,2 +10,4 @@ import re

 def parse_codecs(codecs_str):
+    if not codecs_str:
+        return {}
"""
)


def test_layout_fixtures_have_consistent_hunk_counts():
    assert hunk_counts_match(UNITTEST_DIFF)
    assert hunk_counts_match(YTDLP_DIFF)


def test_weaken_test_turns_an_added_assert_equal_into_assert_true():
    out = weaken_test(UNITTEST_DIFF)
    assert "-        self.assertEqual(parse_codecs('avc1'), {'vcodec': 'avc1'})" in out
    assert "+        self.assertTrue(parse_codecs('avc1'))\n" in out
    assert hunk_counts_match(out)
    assert leaks(out) == []


@pytest.mark.parametrize(
    "line",
    [
        "self.assertEqual(parse_codecs(''), {})",  # falsy expected value: assertTrue would invert it
        "self.assertEqual(a, b, 'message')",  # three arguments: not the simple two-argument form
        "self.assertEqual(",  # split over several lines
    ],
)
def test_weaken_test_skips_assert_equal_forms_it_cannot_weaken_safely(line):
    diff = UNITTEST_DIFF.replace("self.assertEqual(parse_codecs('avc1'), {'vcodec': 'avc1'})", line)
    assert weaken_test(diff) is None


@pytest.mark.parametrize("seed", [0, 1])
def test_code_mutations_go_to_source_files_not_the_singular_test_dir(seed):
    for out in (add_scope_creep(YTDLP_DIFF, seed), add_unused_abstraction(YTDLP_DIFF, seed)):
        test_section = out[: out.index("diff --git a/yt_dlp/")]
        assert "@@ -500,0" not in test_section  # nothing appended to the test file
        new_paths = re.findall(r"^diff --git a/(\S+) b/\S+\nnew file mode", out, re.MULTILINE)
        assert all(p.startswith("yt_dlp/") for p in new_paths)


@pytest.mark.parametrize(
    "diff_line",
    [
        "-    assert payload",
        "+@pytest.mark.skip",
        "+            pytest.skip('flaky')",  # the call form, as in yt-dlp's conftest.py (ade8c2b)
        "-        self.assertEqual(a, b)",
        "+        'skip': 'Geo-restricted',",
        "+        'only_matching': True,",
    ],
)
def test_may_weaken_tests_flags_real_diffs_that_already_weaken_a_test(diff_line):
    assert may_weaken_tests(SRC_DIFF + diff_line + "\n")


def test_may_weaken_tests_flags_a_removed_extractor_test_entry():
    removed = "-    }, {\n-        'url': 'https://example.com/v/1',\n"
    assert may_weaken_tests(SRC_DIFF + removed)
    changed = removed + "+        'url': 'https://example.com/v/2',\n"
    assert not may_weaken_tests(SRC_DIFF + changed)  # a changed URL is not a removed test


def test_may_weaken_tests_passes_an_ordinary_diff():
    assert not may_weaken_tests(SRC_DIFF)
    assert not may_weaken_tests(YTDLP_DIFF)


def test_mutations_handle_a_quoted_path_in_the_diff_header():
    # git quotes paths with spaces or non-ASCII characters: diff --git "a/…" "b/…"
    quoted = YTDLP_DIFF + (
        'diff --git "a/test/testdata/caf\\303\\251.txt" "b/test/testdata/caf\\303\\251.txt"\n'
        'new file mode 100644\n--- /dev/null\n+++ "b/test/testdata/caf\\303\\251.txt"\n@@ -0,0 +1 @@\n+x\n'
    )
    assert add_scope_creep(quoted, seed=1) is not None


def test_parse_repo_reads_optional_source_and_test_dirs():
    assert parse_repo("../yt-dlp=qte77/yt-dlp:yt_dlp,test") == ("../yt-dlp", "qte77/yt-dlp", ("yt_dlp", "test"))
    assert parse_repo("../polyfetch-scrape=qte77/polyfetch-scrape") == (
        "../polyfetch-scrape",
        "qte77/polyfetch-scrape",
        ("src", "tests"),
    )
