# /// script
# requires-python = ">=3.11"
# ///
"""Baseline runner: the same four questions, answered by Claude through the logged-in
Claude Code session (`claude -p`, no API key).

    uv run eval/claude_gate.py [k] [model] [workers] < eval/fixtures.jsonl > eval/run-claude.jsonl

model defaults to "haiku" (the current Haiku); pass a concrete version such as
"claude-haiku-4-5-20251001" to pin one. Each record's model_used shows what answered.
"""

import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from concerns import CONCERNS, state_for

SCHEMA = {
    "type": "object",
    "properties": {name: {"type": "number", "minimum": 0, "maximum": 1} for name in CONCERNS},
    "required": list(CONCERNS),
    "additionalProperties": False,
}

SYSTEM = (
    "You judge a code change from its commit message and diff only. For each question, "
    "give the probability from 0 to 1 that the answer is yes."
)


def build_command(state, model):
    questions = "\n".join(f"{name}: {q}" for name, q in CONCERNS.items())
    prompt = f"Questions:\n{questions}\n\n{state}"
    return [
        "claude",
        "-p",
        prompt,
        # Reason: --bare would skip OAuth and demand ANTHROPIC_API_KEY; --safe-mode keeps the
        # session login but drops this workspace's CLAUDE.md, hooks and plugins.
        "--safe-mode",
        "--tools",
        "",
        "--no-session-persistence",
        # Reason: user settings (e.g. advisorModel, effortLevel) made another model join every
        # call — ~95% of cost, ~7x slower. cwd is a temp dir, so project/local add nothing.
        "--setting-sources",
        "project,local",
        # Reason: with thinking on, Haiku spent ~5k tokens and ~90 s per call on this task.
        "--settings",
        json.dumps({"alwaysThinkingEnabled": False}),
        "--system-prompt",
        SYSTEM,
        "--model",
        model,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
    ]


def cli(argv):
    # Reason: run outside any repo so no project context leaks into the judgment, and give
    # claude empty stdin — it reads piped stdin into the prompt, which leaked the whole
    # fixtures file (labels included) into every call.
    done = subprocess.run(  # noqa: S603
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        check=False,
    )
    return done.stdout


def check(call, state, model):
    out = json.loads(call(build_command(state, model)) or "{}")
    if out.get("is_error") or not isinstance(out.get("structured_output"), dict):
        raise RuntimeError(f"claude -p failed: {out.get('result') or out.get('api_error_status') or 'no output'}")
    return {
        "concerns": {name: float(out["structured_output"][name]) for name in CONCERNS},
        "cost_usd": out.get("total_cost_usd"),
        # Reason: aliases like "opus" resolve server-side; record what actually answered.
        "model_used": ",".join(out.get("modelUsage") or {}) or None,
    }


def run(call, fixtures, k, model, workers=1):
    def one(job):
        fixture, sample = job
        start = time.perf_counter()
        answer = check(call, state_for(fixture), model)
        return {
            "runner": f"claude-{model}",
            "id": fixture["id"],
            "sample": sample,
            "latency_ms": (time.perf_counter() - start) * 1000,
            **answer,
        }

    jobs = [(fixture, sample) for fixture in fixtures for sample in range(k)]
    # Reason: each call is a separate `claude -p` process, so threads give real parallelism;
    # map() keeps output in job order.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(one, jobs)


def main():
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    model = sys.argv[2] if len(sys.argv) > 2 else "haiku"
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    fixtures = [json.loads(line) for line in sys.stdin if line.strip()]
    for record in run(cli, fixtures, k, model, workers):
        print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
