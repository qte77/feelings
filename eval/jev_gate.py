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

from typesafe_sdk import Noul, TypeSafeClient

MODEL = "jev-1.13.0"

# Keep in sync with baml_src/code_gate.baml; test_jev_gate.py enforces it.
CONCERNS = {
    "scope_creep": "Does this change add functionality beyond what its commit message describes?",
    "single_use_abstraction": "Does this change introduce an abstraction (class, interface, helper function, or config parameter) that is used only once?",
    "duplication": "Does this change duplicate logic that already appears elsewhere in the same diff?",
    "weakened_tests": "Does this change weaken, skip, or delete tests or assertions?",
}


def state_for(fixture):
    return f"Commit message:\n{fixture['message']}\n\nDiff:\n{fixture['diff']}"


def check(client, state):
    questions = {name: Noul(instructions=q) for name, q in CONCERNS.items()}
    response = client.system_one(state, questions, model=MODEL)
    return {name: response.nouls[name].noul for name in CONCERNS}


def run(client, fixtures, k):
    for fixture in fixtures:
        state = state_for(fixture)
        for sample in range(k):
            start = time.perf_counter()
            concerns = check(client, state)
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
