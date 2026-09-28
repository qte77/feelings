# /// script
# requires-python = ">=3.11"
# dependencies = ["typesafe-sdk==0.7.1"]
# ///
"""Local, non-blocking Jev check of the commits you're about to push (plan row 24).

    uv run eval/jev_check.py [<range>]          # default: @{upstream}..HEAD, else HEAD~1..HEAD
    git config core.hooksPath .githooks         # once: run it on every `git push`

Checks the diff without data and lockfiles (*.json, *.jsonl, *.lock). Prints the four probabilities, names any at or above JEV_CHECK_AT (default 0.70) as worth a
closer look, appends one line to JEV_CHECK_LOG (default .git/jev-check.jsonl) and always exits 0.
Needs TYPESAFE_API_KEY; without it, or on any API error, it says "skipped" and the push goes on.
"""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime

from typesafe_sdk import TypeSafeAPIError, TypeSafeClient

from concerns import state_for
from jev_gate import check, cost_usd

AT = float(os.environ.get("JEV_CHECK_AT", "0.70"))
# Reason: Jev takes 32k tokens for the state plus the longest question; ~4 chars per token.
MAX_STATE_CHARS = 100_000


def review(client, message, diff, at=AT):
    """One Jev call on a commit message and diff: the four answers, what's flagged, time and cost."""
    start = time.perf_counter()
    try:
        concerns, usage = check(client, state_for({"message": message, "diff": diff}))
    except TypeSafeAPIError as e:
        return {"error": type(e).__name__}
    return {
        "concerns": concerns,
        "flagged": [name for name, p in concerns.items() if p >= at],
        "latency_ms": (time.perf_counter() - start) * 1000,
        "cost_usd": cost_usd(usage["input_tokens"]),
    }


def report(record, at=AT):
    if "error" in record:
        return f"jev-check: skipped ({record['error']}); the push goes on."
    lines = [f"jev-check (flags at {at:.2f}; it never blocks):"]
    for name, p in record["concerns"].items():
        mark = "  <- worth a closer look" if name in record["flagged"] else ""
        lines.append(f"  {name:<24} {p:.2f}{mark}")
    if not record["flagged"]:
        lines.append("  nothing flagged")
    return "\n".join(lines)


def log(path, record):
    """Append one line; `verdict` stays null until you label it (how: the plan, row 24)."""
    entry = {"time": datetime.now(UTC).isoformat(timespec="seconds"), "verdict": None, **record}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _git(*args):
    # Reason: fixed git argv; the range comes from git's own pre-push input or the operator.
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def _default_range():
    try:
        _git("rev-parse", "--verify", "--quiet", "@{upstream}")
        return "@{upstream}..HEAD"
    except subprocess.CalledProcessError:
        return "HEAD~1..HEAD"


def main(argv):
    rng = argv[0] if argv else _default_range()
    record = {"range": rng}
    # Reason: a local advisory check must never stop a push, whatever fails (no key, no network,
    # a bad range, a firewall block): report it as skipped and exit 0.
    try:
        message = _git("log", "--format=%B", rng).strip()
        # Data and lockfiles aren't code changes and would crowd out the code in Jev's input.
        diff = _git("diff", rng, "--", ".", ":!*.json", ":!*.jsonl", ":!*.lock")
        if not diff.strip():
            print("jev-check: nothing to check.")
            return 0
        if len(message) + len(diff) > MAX_STATE_CHARS:
            record["error"] = "TooLarge"
        else:
            with TypeSafeClient() as client:
                record.update(review(client, message, diff))
    except Exception as e:  # noqa: BLE001
        record["error"] = type(e).__name__
    print(report(record))
    try:
        log(os.environ.get("JEV_CHECK_LOG") or _git("rev-parse", "--git-path", "jev-check.jsonl").strip(), record)
    except Exception as e:  # noqa: BLE001
        print(f"jev-check: log not written ({type(e).__name__}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
