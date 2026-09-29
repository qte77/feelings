# /// script
# requires-python = ">=3.11"
# ///
"""Build labelled code-gate fixtures from public repos' history.

    uv run eval/fixtures_build.py eval/fixtures.jsonl <n_sources> <first_index> <path>=<owner/repo>[:<dir>,…] ... > new.jsonl

The optional dirs name where a repo keeps code and tests (default `src,tests`; yt-dlp: `yt_dlp,test`).

Each source commit yields one good fixture (its real diff) and three bad fixtures made by
mutating that same diff, so good and bad differ only by the problem. Commits already used
by the existing fixtures are skipped, and sources are picked to serve the scarcest concern
first. Mutations follow eval/fixtures.README.md; the lines a mutation adds are checked with
leaks() so they never name their own problem.
"""

import ast
import difflib
import json
import re
import subprocess
import sys
import textwrap
from collections import Counter

CONCERN_NAMES = ("scope_creep", "single_use_abstraction", "duplication", "weakened_tests")

# Words that would give away the label if they appeared in added code or comments.
LEAK_WORDS = ("duplicate", "copy", "unused", "dead", "again", "repeat", "secondary", "weaken", "loosen", "scope")

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")

# Neutral templates: config-like objects, named for plausible purposes, never for their problem.
_ABSTRACTIONS = (
    ("RetryBudget", "attempts", "int", "3", "Retry budget for outbound calls."),
    ("CacheSettings", "ttl_seconds", "int", "300", "Cache settings for fetched pages."),
    ("OutputLayout", "indent", "int", "2", "Layout options for written reports."),
    ("BatchWindow", "size", "int", "50", "Batch window for bulk operations."),
    ("RenderOptions", "width", "int", "80", "Rendering options for console output."),
    ("PollingInterval", "seconds", "float", "5.0", "Polling interval for background refresh."),
)

# Functionality no ordinary commit message in these repos describes.
_UNRELATED = (
    ("slugify", ["text"], ["    import re", "", '    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")']),
    (
        "rows_to_csv",
        ["rows"],
        [
            "    import csv",
            "    import io",
            "",
            "    buf = io.StringIO()",
            "    csv.writer(buf).writerows(rows)",
            "    return buf.getvalue()",
        ],
    ),
    (
        "parse_duration",
        ["value"],
        ['    units = {"s": 1, "m": 60, "h": 3600}', "", "    return int(value[:-1]) * units[value[-1]]"],
    ),
    (
        "human_bytes",
        ["size"],
        [
            '    for unit in ("B", "KB", "MB", "GB"):',
            "        if size < 1024:",
            '            return f"{size:.0f} {unit}"',
            "        size /= 1024",
            '    return f"{size:.0f} TB"',
        ],
    ),
)

_SUFFIXES = ("for_report", "for_export", "for_batch", "for_cli", "for_cache", "for_preview")


def _snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _files(diff):
    """[(path, start, end)] offsets of each file section in the diff."""
    starts = [m.start() for m in re.finditer(r"^diff --git ", diff, re.MULTILINE)]
    out = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(diff)
        # Reason: git quotes paths with spaces or non-ASCII characters: diff --git "a/…" "b/…".
        path = re.match(r'diff --git "?a/(.+?)"? "?b/', diff[s:]).group(1)
        out.append((path, s, end))
    return out


def _append_hunk(diff, path, added_lines):
    """Add a synthetic trailing hunk to an existing file section of the diff."""
    for p, _, end in _files(diff):
        if p == path:
            block = [""] + added_lines
            hunk = f"@@ -500,0 +501,{len(block)} @@\n" + "".join(f"+{line}\n" for line in block)
            return diff[:end] + hunk + diff[end:]
    return None


def _new_file(path, lines):
    body = "".join(f"+{line}\n" for line in lines)
    return (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..0000000\n"
        f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"
    )


def _join(diff, extra):
    return diff + ("" if diff.endswith("\n") else "\n") + extra


def _is_test(path):
    """tests/… (pytest layout), test/… (yt-dlp's unittest layout) or a test_*.py file."""
    return path.split("/", 1)[0] in ("test", "tests") or path.rsplit("/", 1)[-1].startswith("test_")


def _code_files(diff):
    return [p for p, _, _ in _files(diff) if p.endswith(".py") and not _is_test(p)]


def _source_dir(diff):
    paths = _code_files(diff)
    return paths[0].rsplit("/", 1)[0] if paths and "/" in paths[0] else "src"


_FALSY = {"0", "0.0", "False", "None", '""', "''", "[]", "{}", "()", "set()"}


def _balanced(text):
    """True when the == is top-level, i.e. the text left of it closes every bracket it opens."""
    return all(text.count(o) == text.count(c) for o, c in ("()", "[]", "{}"))


def _args(text):
    """Split call arguments at top-level commas, ignoring commas inside brackets or quotes."""
    out, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(text):
        if quote:
            quote = None if ch == quote and text[i - 1] != "\\" else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
    out.append(text[start:].strip())
    return out


def _weaker(line):
    """The weaker replacement for one added assert line, or None when it can't be weakened safely.

    `assert A == B` -> `assert A`; `self.assertEqual(A, B)` -> `self.assertTrue(A)`.
    Reason: with a falsy B, dropping it inverts the test instead of weakening it.
    """
    m = re.match(r"^\+(\s*)assert (.+?) == (.+)$", line)
    if m and m.group(3).strip() not in _FALSY and _balanced(m.group(2)):
        return f"+{m.group(1)}assert {m.group(2)}"
    m = re.match(r"^\+(\s*)self\.assertEqual\((.*)\)$", line)
    if m and _balanced(m.group(2)):
        args = _args(m.group(2))
        if len(args) == 2 and args[1] not in _FALSY:
            return f"+{m.group(1)}self.assertTrue({args[0]})"
    return None


def weaken_test(diff):
    """Turn an added equality assert into a visible `-` original / `+` weaker pair."""
    lines = diff.splitlines(keepends=True)
    header = None
    for i, line in enumerate(lines):
        if _HUNK.match(line):
            header = i
        weaker = _weaker(line.rstrip("\n"))
        if weaker and header is not None:
            h = _HUNK.match(lines[header])
            old_start, old_n, new_start, new_n, tail = h.groups()
            old_n = int(old_n or 1) + 1
            lines[header] = f"@@ -{old_start},{old_n} +{new_start},{new_n or 1} @@{tail}\n"
            lines[i] = f"-{line[1:]}" + ("" if line.endswith("\n") else "\n") + f"{weaker}\n"
            return "".join(lines)
    return None


def _free(options, seed, diff, names):
    """First option from `seed` on whose names don't already occur in the diff (None if all do)."""
    for k in range(len(options)):
        option = options[(seed + k) % len(options)]
        if not any(re.search(rf"\b{re.escape(n)}\b", diff, re.IGNORECASE) for n in names(option)):
            return option
    return None


def add_unused_abstraction(diff, seed):
    """A new private class, instantiated once at module level; nothing else uses the result."""
    option = _free(_ABSTRACTIONS, seed, diff, lambda o: (o[0], _snake(o[0])))
    if option is None:
        return None
    cls, field, typ, default, doc = option
    cls = f"_{cls}"
    var = f"_{_snake(cls[1:])}"
    lines = [
        f'"""{doc}"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        f"class {cls}:",
        f"    {field}: {typ} = {default}",
        "",
        "",
        f"{var} = {cls}()",
    ]
    return _join(diff, _new_file(f"{_source_dir(diff)}/_{_snake(cls[1:])}.py", lines))


def _depth(text):
    return sum(text.count(o) - text.count(c) for o, c in ("()", "[]", "{}"))


def add_duplication(diff, seed):
    """A near-copy of a function added in the same diff, under a neutral name, in the same file."""
    for path, start, end in _files(diff):
        section = diff[start:end].splitlines()
        for i, line in enumerate(section):
            m = re.match(r"^\+def (\w+)\((.*)$", line)
            if not m:
                continue
            body, depth = [line[1:]], _depth(line[1:])
            for nxt in section[i + 1 :]:
                text = nxt[1:]
                # Reason: an unindented line ends the function only once the signature's brackets close.
                if not nxt.startswith("+") or (depth <= 0 and text and not text.startswith((" ", "\t"))):
                    break
                body.append(text)
                depth += _depth(text)
            while body and not body[-1].strip():
                body.pop()
            try:
                ast.parse("\n".join(body))
            except SyntaxError:
                continue  # only partly added in this diff; try the next function
            original = m.group(1)
            suffix = _free(_SUFFIXES, seed, diff, lambda s: (f"{original}_{s}",))  # noqa: B023 - used immediately
            if suffix is None:
                return None
            name = f"{original}_{suffix}"
            body[0] = f"def {name}({m.group(2)}"
            return _append_hunk(diff, path, ["", *body])
    return None


_SYNTHETIC_HUNK = re.compile(r"^@@ -500,0 \+501,(\d+) @@$", re.MULTILINE)
# _HUNK itself isn't MULTILINE (it's normally matched one line at a time); this variant finds
# every hunk header inside a multi-line section.
_HUNK_ML = re.compile(_HUNK.pattern, re.MULTILINE)

# Lines assumed to separate the last real hunk from the synthetic one; real diffs don't put
# two hunks back to back (git's default 3-line context would have merged them into one).
_HEADER_GAP = 20


def realistic_headers(diff):
    """Rewrite each synthetic `@@ -500,0 +501,N @@` header to continue after that file section's
    last real hunk, instead of the fixed `-500,0`/`+501` cue `_append_hunk` writes.

    Only the header numbers move; the hunk body (what it adds) is untouched. A section whose
    synthetic hunk has no real hunk before it is left alone.
    """
    out, cursor = [], 0
    for _path, start, end in _files(diff):
        section = diff[start:end]
        synthetic = _SYNTHETIC_HUNK.search(section)
        if not synthetic:
            continue
        real = None
        for m in _HUNK_ML.finditer(section[: synthetic.start()]):
            real = m
        if real is None:
            continue
        old_start, old_n, new_start, new_n = (int(real.group(i) or 1) for i in (1, 2, 3, 4))
        new_old_start = old_start + old_n + _HEADER_GAP
        offset = (new_start + new_n) - (old_start + old_n)
        new_new_start = new_old_start + offset
        header = f"@@ -{new_old_start},0 +{new_new_start},{synthetic.group(1)} @@"
        abs_start, abs_end = start + synthetic.start(), start + synthetic.end()
        out.append(diff[cursor:abs_start])
        out.append(header)
        cursor = abs_end
    out.append(diff[cursor:])
    return "".join(out)


_NEW_FILE_HUNK = re.compile(r"^@@ -0,0 \+1,(\d+) @@\n", re.MULTILINE)

# `_new_file` always writes a null before-hash *and* a null after-hash (`index 0000000..0000000`)
# because it invents no blob. A real commit's own new file always gets a real after-hash, so this
# marks the section as mutation-added rather than one the source commit itself already added (a
# source commit can legitimately add a file of its own, e.g. an extracted helper module).
_SYNTHETIC_NEW_FILE = "new file mode 100644\nindex 0000000..0000000\n"


def inline_new_files(diff):
    """Move a mutation-added `new file mode` section's lines into an existing non-test source
    file section of the same diff, as an appended hunk with a realistic header (via
    `realistic_headers`). Records built by `add_unused_abstraction` and odd-seed
    `add_scope_creep` have exactly one such section.

    Left unchanged when there is no mutation-added new-file section (a real one the source
    commit added itself is left alone), or no other non-test `.py` file to move its lines into.
    """
    for path, start, end in _files(diff):
        section = diff[start:end]
        if _SYNTHETIC_NEW_FILE not in section:
            continue
        hunk = _NEW_FILE_HUNK.search(section)
        if not hunk:
            continue
        lines = [line[1:] for line in section[hunk.end() :].splitlines() if line.startswith("+")]
        target = next(
            (
                p
                for p, s2, e2 in _files(diff)
                if p != path and p.endswith(".py") and not _is_test(p) and "new file mode" not in diff[s2:e2]
            ),
            None,
        )
        if target is None:
            continue
        without = diff[:start] + diff[end:]
        appended = _append_hunk(without, target, lines)
        if appended is None:
            continue
        return realistic_headers(appended)
    return diff


def add_scope_creep(diff, seed):
    """An unrelated function: inside an existing file on even seeds, as a new file on odd ones."""
    option = _free(_UNRELATED, seed, diff, lambda o: (o[0],))
    if option is None:
        return None
    name, args, body = option
    func = [f"def {name}({', '.join(args)}):", *body]
    if seed % 2 == 0:
        src = _code_files(diff)
        if src:
            return _append_hunk(diff, src[0], ["", *func])
    return _join(diff, _new_file(f"{_source_dir(diff)}/{name}.py", func))


MUTATIONS = {
    "scope_creep": add_scope_creep,
    "single_use_abstraction": add_unused_abstraction,
    "duplication": add_duplication,
    "weakened_tests": lambda diff, seed: weaken_test(diff),
}


def added_by(original, mutated):
    """The added (+) lines a mutation introduced, i.e. in `mutated` but not in `original`."""
    extra = Counter(_plus_lines(mutated)) - Counter(_plus_lines(original))
    out = []
    for line in _plus_lines(mutated):
        if extra[line]:
            extra[line] -= 1
            out.append(line + "\n")
    return "".join(out)


def parses(original, mutated):
    """True when the code a mutation inserted is valid Python on its own.

    Uses the inserted block itself (difflib), not added_by(): a duplicated body repeats lines
    the original already adds, so a line-count difference would drop them.
    """
    old, new = original.splitlines(), mutated.splitlines()
    inserted = []
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag in ("insert", "replace"):
            inserted += [line[1:] for line in new[j1:j2] if line.startswith("+") and not line.startswith("+++")]
    code = textwrap.dedent("\n".join(inserted))
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


def _plus_lines(diff):
    return [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]


def select(pool, counts, n_sources):
    """Pick n sources and three bad concerns each, always serving the scarcest concern first.

    pool: [(source, {concern: mutated_diff})], newest first; counts: bad fixtures per concern so far.
    Returns [(source, [(concern, mutated_diff), ...])]. Sources with fewer than 3 options are skipped.
    """
    counts, picked, used = dict(counts), [], set()
    while len(picked) < n_sources:
        scarce = sorted(counts, key=lambda c: counts[c])
        choice = None
        for concern in scarce:
            choice = next(
                (
                    i
                    for i, (_, options) in enumerate(pool)
                    if i not in used and len(options) >= 3 and concern in options
                ),
                None,
            )
            if choice is not None:
                break
        if choice is None:
            break
        used.add(choice)
        source, options = pool[choice]
        chosen = sorted(options, key=lambda c: counts[c])[:3]
        for concern in chosen:
            counts[concern] += 1
        picked.append((source, [(c, options[c]) for c in chosen]))
    return picked


_WEAKENING = re.compile(
    r"^-\s*(assert |self\.assert)"  # an existing assert removed
    r"|^\+.*(pytest\.(mark\.)?skip|unittest\.skip)"  # a test skipped (decorator or call)
    r"|^\+\s*['\"](skip['\"]\s*:|only_matching['\"]\s*:\s*True)",  # yt-dlp: an extractor test skipped
    re.MULTILINE,
)
_TEST_URL = re.compile(r"^([-+])\s*['\"]url['\"]\s*:", re.MULTILINE)


def may_weaken_tests(diff):
    """True when a real diff may already weaken a test, so it can't serve as a clean example."""
    urls = Counter(m.group(1) for m in _TEST_URL.finditer(diff))
    # Reason: more removed than added extractor-test URLs means a _TESTS entry was deleted.
    return bool(_WEAKENING.search(diff)) or urls["-"] > urls["+"]


def parse_repo(spec):
    """`<path>=<owner/repo>[:<dir>,<dir>…]` -> (path, slug, dirs); dirs default to src and tests."""
    path, rest = spec.split("=", 1)
    slug, _, dirs = rest.partition(":")
    return path, slug, tuple(dirs.split(",")) if dirs else ("src", "tests")


def leaks(diff):
    """Leak words found in added lines only (removed lines are the author's, not ours)."""
    added = " ".join(
        line[1:].lower() for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    return [w for w in LEAK_WORDS if re.search(rf"(?<![a-z]){w}", added)]


# Git walking below is thin glue; the rule is no unit tests for it.

_SKIP_MESSAGE = re.compile(r"^(chore\(deps|build\(deps|style|ci|docs)|bump|changelog|format|rename", re.IGNORECASE)


def _git(repo, *args):
    # Reason: fixed git argv; the repo path comes from the operator's command line.
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def candidates(repo, dirs=("src", "tests")):
    """(sha, message, diff) for real commits under `dirs` of a usable size, newest first."""
    for sha in _git(repo, "rev-list", "--no-merges", "HEAD", "--", *dirs).split():
        message = _git(repo, "log", "-1", "--format=%B", sha).strip()
        if _SKIP_MESSAGE.search(message.splitlines()[0]):
            continue
        diff = _git(repo, "show", "--format=", "--patch", sha, "--", *dirs)
        # Skip commits whose real diff may already weaken tests, so "good" stays good.
        if not 400 <= len(diff) <= 12000 or may_weaken_tests(diff):
            continue
        yield sha, message, diff


def build(repos, existing, n_sources, first_index):
    """repos: [(path, slug, dirs)]; existing: current fixtures (their shas are skipped, their counts kept)."""
    used_shas = {f["source_sha"] for f in existing}
    counts = Counter({c: 0 for c in CONCERN_NAMES})
    counts.update(c for f in existing for c, bad in f["expect"].items() if bad)
    pool = []
    for path, slug, dirs in repos:
        for sha, message, diff in candidates(path, dirs):
            if sha in used_shas:
                continue
            options = {}
            for concern, mutate in MUTATIONS.items():
                mutated = mutate(diff, len(pool))
                if mutated and not leaks(added_by(diff, mutated)) and parses(diff, mutated):
                    options[concern] = mutated
            pool.append(((slug, sha, message, diff), options))
    records = []
    for n, ((slug, sha, message, diff), bad) in enumerate(select(pool, counts, n_sources)):
        idx = f"{first_index + n:02d}"
        base = {"source_repo": slug, "source_sha": sha, "message": message}
        records.append(
            {"id": f"good-{idx}-{sha[:7]}", **base, "diff": diff, "expect": dict.fromkeys(CONCERN_NAMES, False)}
        )
        for concern, mutated in bad:
            expect = {c: c == concern for c in CONCERN_NAMES}
            records.append({"id": f"bad-{idx}-{concern}-{sha[:7]}", **base, "diff": mutated, "expect": expect})
    return records


VARIANTS = {"headers": realistic_headers, "inline": inline_new_files}


def build_variant(records, transform):
    """Apply `transform` to every bad-* record's diff; good-* records pass through unchanged.

    Returns (records, changed, unchanged), counting bad-* records whose diff `transform` did
    or didn't alter.
    """
    out, changed, unchanged = [], 0, 0
    for record in records:
        if not record["id"].startswith("bad-"):
            out.append(record)
            continue
        new_diff = transform(record["diff"])
        if new_diff != record["diff"]:
            changed += 1
        else:
            unchanged += 1
        out.append({**record, "diff": new_diff})
    return out, changed, unchanged


def main():
    args = sys.argv[1:]
    if args and args[0] == "--variant":
        _, kind, path = args
        with open(path, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        out, changed, unchanged = build_variant(records, VARIANTS[kind])
        for record in out:
            print(json.dumps(record))
        print(f"{kind}: changed {changed}, unchanged {unchanged}", file=sys.stderr)
        return
    existing_path, n_sources, first_index, *repos = args
    with open(existing_path, encoding="utf-8") as f:
        existing = [json.loads(line) for line in f if line.strip()]
    for record in build([parse_repo(r) for r in repos], existing, int(n_sources), int(first_index)):
        print(json.dumps(record))


if __name__ == "__main__":
    main()
