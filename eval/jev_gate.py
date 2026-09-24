# /// script
# requires-python = ">=3.11"
# dependencies = ["typesafe-sdk==0.7.1"]
# ///
"""Python half of the Jev code-gate comparison.

uv run eval/jev_gate.py [k] < eval/fixtures.jsonl > eval/run-python.jsonl
"""

import json
import sys
import time

from typesafe_sdk import Noul, TypeSafeAPIError, TypeSafeClient

from concerns import CONCERNS, state_for

MODEL = "jev-1.13.0"
# typesafe.ai homepage: "$42 Per Billion input tokens" (checked 2026-09-24). No output price is
# published, so cost_usd covers input tokens only.
INPUT_USD_PER_M = 0.042


def check(client, state):
    questions = {name: Noul(instructions=q) for name, q in CONCERNS.items()}
    response = client.system_one(state, questions, model=MODEL)
    concerns = {name: response.nouls[name].noul for name in CONCERNS}
    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    return concerns, usage


def cost_usd(input_tokens):
    # Unknown, not free: None when the API didn't report usage.
    return None if input_tokens is None else input_tokens * INPUT_USD_PER_M / 1_000_000


def run(client, fixtures, k):
    for fixture in fixtures:
        state = state_for(fixture)
        for sample in range(k):
            start = time.perf_counter()
            try:
                concerns, usage = check(client, state)
            except TypeSafeAPIError as e:
                # Reason: TypeSafe's Cloudflare WAF 403s some diffs on content alone, every time.
                # Record it, skip this fixture's remaining repeats, keep the run going.
                yield {"runner": "python", "id": fixture["id"], "sample": sample, "error": type(e).__name__}
                break
            latency_ms = (time.perf_counter() - start) * 1000
            yield {
                "runner": "python",
                "id": fixture["id"],
                "sample": sample,
                "latency_ms": latency_ms,
                "concerns": concerns,
                **usage,
                "cost_usd": cost_usd(usage["input_tokens"]),
            }


def main():
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    fixtures = [json.loads(line) for line in sys.stdin if line.strip()]
    with TypeSafeClient() as client:
        for record in run(client, fixtures, k):
            print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
