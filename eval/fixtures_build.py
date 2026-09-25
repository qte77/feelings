# /// script
# requires-python = ">=3.11"
# ///
"""Build labelled code-gate fixtures from public repos' history.

    uv run eval/fixtures_build.py eval/fixtures.jsonl <n_sources> <first_index> <path>=<owner/repo> ... > new.jsonl

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
        path = re.match(r"diff --git a/(\S+) b/", diff[s:]).group(1)
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


def _source_dir(diff):
    paths = [p for p, _, _ in _files(diff) if p.endswith(".py") and not p.startswith("tests")]
    return paths[0].rsplit("/", 1)[0] if paths and "/" in paths[0] else "src"


_FALSY = {"0", "0.0", "False", "None", '""', "''", "[]", "{}", "()", "set()"}


def _balanced(text):
    """True when the == is top-level, i.e. the text left of it closes every bracket it opens."""
    return all(text.count(o) == text.count(c) for o, c in ("()", "[]", "{}"))


def weaken_test(diff):
    """Turn an added `assert A == B` into a visible `- assert A == B` / `+ assert A`."""
    lines = diff.splitlines(keepends=True)
    header = None
    for i, line in enumerate(lines):
        if _HUNK.match(line):
            header = i
        m = re.match(r"^\+(\s*)assert (.+?) == (.+)$", line.rstrip("\n"))
        # Reason: `assert A == <falsy>` -> `assert A` inverts the test instead of weakening it.
        if m and header is not None and m.group(3).strip() not in _FALSY and _balanced(m.group(2)):
            indent, left = m.group(1), m.group(2)
            h = _HUNK.match(lines[header])
            old_start, old_n, new_start, new_n, tail = h.groups()
            old_n = int(old_n or 1) + 1
            lines[header] = f"@@ -{old_start},{old_n} +{new_start},{new_n or 1} @@{tail}\n"
            lines[i] = f"-{line[1:]}" + ("" if line.endswith("\n") else "\n") + f"+{indent}assert {left}\n"
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


def add_scope_creep(diff, seed):
    """An unrelated function: inside an existing file on even seeds, as a new file on odd ones."""
    option = _free(_UNRELATED, seed, diff, lambda o: (o[0],))
    if option is None:
        return None
    name, args, body = option
    func = [f"def {name}({', '.join(args)}):", *body]
    if seed % 2 == 0:
        src = [p for p, _, _ in _files(diff) if p.endswith(".py") and not p.startswith("tests")]
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


def candidates(repo):
    """(sha, message, diff) for real src/tests commits of a usable size, newest first."""
    for sha in _git(repo, "rev-list", "--no-merges", "HEAD", "--", "src", "tests").split():
        message = _git(repo, "log", "-1", "--format=%B", sha).strip()
        if _SKIP_MESSAGE.search(message.splitlines()[0]):
            continue
        diff = _git(repo, "show", "--format=", "--patch", sha, "--", "src", "tests")
        # Skip commits whose real diff may already weaken tests, so "good" stays good.
        if not 400 <= len(diff) <= 12000 or re.search(r"^-\s*assert |^\+.*pytest\.mark\.skip", diff, re.MULTILINE):
            continue
        yield sha, message, diff


def build(repos, existing, n_sources, first_index):
    """repos: [(path, slug)]; existing: current fixtures (their shas are skipped, their counts kept)."""
    used_shas = {f["source_sha"] for f in existing}
    counts = Counter({c: 0 for c in CONCERN_NAMES})
    counts.update(c for f in existing for c, bad in f["expect"].items() if bad)
    pool = []
    for path, slug in repos:
        for sha, message, diff in candidates(path):
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


def main():
    existing_path, n_sources, first_index, *repos = sys.argv[1:]
    with open(existing_path, encoding="utf-8") as f:
        existing = [json.loads(line) for line in f if line.strip()]
    pairs = [tuple(r.split("=", 1)) for r in repos]
    for record in build(pairs, existing, int(n_sources), int(first_index)):
        print(json.dumps(record))


if __name__ == "__main__":
    main()
