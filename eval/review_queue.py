# /// script
# requires-python = ">=3.11"
# ///
"""Build the label review queue for the owner (plan 0002, row P3).

Selects, on the first answer (sample 0) at the 0.70 setting:
- a clean record (no labelled concern) that every answering setup flags (any concern >= 0.70);
- a flawed record, for each of its labelled concerns that every answering setup misses
  (scores < 0.70) -- most records have one labelled concern, a few have two;
- plus any id passed with --also, whether or not it qualifies on its own.

A setup that errored, or never answered a given id, is left out of "every setup that answered"
for that id; a record with no answering setup at all does not auto-qualify.

Writes Markdown, sorted into two sections (flawed-missed, then clean-flagged), one entry per
record: id, source repo + short sha, the message's first line, the label, each setup's max
concern and score, a short excerpt of the diff's added lines, and a blank "Owner verdict" line.

    uv run eval/review_queue.py <fixtures.jsonl> <out.md> [--heading TEXT] [--also <id>]... \\
        <Name>=<run.jsonl>...
"""

import sys

from metrics import REJECT_AT, load_jsonl


def true_concerns(fixture):
    return [c for c, v in fixture["expect"].items() if v]


def is_clean(fixture):
    return not true_concerns(fixture)


def first_answers(records):
    """id -> concerns dict, from sample 0 among records that answered (no error)."""
    return {r["id"]: r["concerns"] for r in records if r.get("sample") == 0 and "error" not in r}


def every_setup_flags(answers, at=REJECT_AT):
    """True if every (name, concerns) pair in `answers` has some concern >= at. False with no answers."""
    return bool(answers) and all(any(v >= at for v in concerns.values()) for _, concerns in answers)


def missed_concerns(fixture, answers, at=REJECT_AT):
    """Labelled concerns every answering setup scores below `at`. Empty with no answers."""
    if not answers:
        return []
    return [c for c in true_concerns(fixture) if all(concerns[c] < at for _, concerns in answers)]


def select(fixtures, runs, also=(), at=REJECT_AT):
    """runs: [(name, records)]. Returns a list of {fixture, answers, reason, missed}."""
    per_setup = {name: first_answers(records) for name, records in runs}
    also = set(also)
    selected = []
    for fixture in fixtures:
        fid = fixture["id"]
        answers = [(name, per_setup[name][fid]) for name in per_setup if fid in per_setup[name]]
        if is_clean(fixture):
            missed = []
            auto = every_setup_flags(answers, at)
        else:
            missed = missed_concerns(fixture, answers, at)
            auto = bool(missed)
        if auto or fid in also:
            selected.append(
                {"fixture": fixture, "answers": answers, "reason": "auto" if auto else "requested", "missed": missed}
            )
    return selected


def added_lines(diff, limit=15):
    """The diff's added-code lines (`+...`), excluding the `+++` file header, up to `limit`."""
    lines = [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    return lines[:limit]


def render_record(fixture, answers, reason, missed):
    fid = fixture["id"]
    short_sha = fixture.get("source_sha", "")[:7]
    message = fixture.get("message", "")
    first_line = message.splitlines()[0] if message else ""
    concerns = true_concerns(fixture)
    label = ", ".join(concerns) if concerns else "clean"
    if missed:
        label += f" — questioned: {', '.join(missed)}"

    lines = [f"#### `{fid}`", ""]
    lines.append(f"- **source**: `{fixture.get('source_repo', '?')}`@`{short_sha}`")
    lines.append(f"- **message**: {first_line}")
    lines.append(f"- **label**: {label}")
    if reason == "requested":
        lines.append("- **why here**: requested via `--also`, not auto-selected at the 0.70 setting")
    lines.append("- **scores** (max concern, first answer):")
    if answers:
        for name, setup_concerns in answers:
            cname = max(setup_concerns, key=setup_concerns.get)
            lines.append(f"  - {name}: `{cname}` {setup_concerns[cname]:.2f}")
    else:
        lines.append("  - (no setup answered this record)")
    lines.append("")

    added = added_lines(fixture.get("diff", ""))
    if added:
        lines.append("```diff")
        lines.extend(added)
        lines.append("```")
        lines.append("")

    lines.append("**Owner verdict** (keep / relabel to … / drop, with reason): ")
    lines.append("")
    return "\n".join(lines)


def render(fixtures, runs, also=(), heading=None, at=REJECT_AT):
    selected = select(fixtures, runs, also, at)
    flawed = sorted(
        (item for item in selected if not is_clean(item["fixture"])), key=lambda item: item["fixture"]["id"]
    )
    clean = sorted((item for item in selected if is_clean(item["fixture"])), key=lambda item: item["fixture"]["id"])

    parts = []
    if heading:
        parts.append(f"## {heading}")
        parts.append("")
    parts.append(f"### Flawed, missed by every setup ({len(flawed)})")
    parts.append("")
    for item in flawed:
        parts.append(render_record(item["fixture"], item["answers"], item["reason"], item["missed"]))
    parts.append(f"### Clean, flagged by every setup ({len(clean)})")
    parts.append("")
    for item in clean:
        parts.append(render_record(item["fixture"], item["answers"], item["reason"], item["missed"]))
    return "\n".join(parts)


def parse_args(argv):
    """<fixtures> <out> [--heading TEXT] [--also <id>]... <Name>=<run.jsonl>..., any order."""
    positional = []
    runs = []
    also = []
    heading = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--also":
            i += 1
            also.append(argv[i])
        elif tok == "--heading":
            i += 1
            heading = argv[i]
        elif "=" in tok:
            name, path = tok.split("=", 1)
            runs.append((name, path))
        else:
            positional.append(tok)
        i += 1
    fixtures_path, out_path = positional
    return fixtures_path, out_path, runs, also, heading


def main(argv):
    fixtures_path, out_path, run_specs, also, heading = parse_args(argv)
    fixtures = load_jsonl(fixtures_path)
    runs = [(name, load_jsonl(path)) for name, path in run_specs]
    text = render(fixtures, runs, also=also, heading=heading)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
