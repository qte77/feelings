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


def check(client, state):
    questions = {name: Noul(instructions=q) for name, q in CONCERNS.items()}
    response = client.system_one(state, questions, model=MODEL)
    return {name: response.nouls[name].noul for name in CONCERNS}


def run(client, fixtures, k):
    for fixture in fixtures:
        state = state_for(fixture)
        for sample in range(k):
            start = time.perf_counter()
            try:
                concerns = check(client, state)
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
            }


def main():
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    fixtures = [json.loads(line) for line in sys.stdin if line.strip()]
    with TypeSafeClient() as client:
        for record in run(client, fixtures, k):
            print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
