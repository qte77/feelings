import json
import re
from pathlib import Path

import httpx2
import pytest
from typesafe_sdk import TypeSafeClient

from jev_gate import CONCERNS, INPUT_USD_PER_M, MODEL, check, cost_usd, run, state_for

FIXTURE = {"id": "good-01", "message": "Add retry to fetch", "diff": "+    retry(fetch)\n"}


def fake_client(seen, noul=0.25):
    """A TypeSafe client whose HTTP goes to a local fake, so no key or spend is needed."""

    def handler(request):
        body = json.loads(request.content)
        seen.append({"url": str(request.url), "body": body})
        answers = {name: {"type": "noul", "noul": noul} for name in body["questions"]}
        return httpx2.Response(200, json={"model": body["model"], "usage": {"input_tokens": 1}, "answers": answers})

    return TypeSafeClient(api_key="test", transport=httpx2.MockTransport(handler))


def test_one_request_with_four_noul_questions_on_the_pinned_model():
    seen = []
    check(fake_client(seen), state_for(FIXTURE))
    assert len(seen) == 1
    body = seen[0]["body"]
    assert seen[0]["url"] == "https://api.typesafe.ai/v1/systemone"
    assert body["model"] == MODEL == "jev-1.13.0"
    assert body["questions"] == {name: {"type": "noul", "instructions": q} for name, q in CONCERNS.items()}


def test_state_carries_message_and_diff():
    state = state_for(FIXTURE)
    assert "Add retry to fetch" in state
    assert "+    retry(fetch)" in state


def test_check_returns_one_probability_per_concern_and_the_token_usage():
    concerns, usage = check(fake_client([], noul=0.8), "state")
    assert concerns == {name: 0.8 for name in CONCERNS}
    assert usage == {"input_tokens": 1, "output_tokens": None}  # the fake reports input tokens only


def test_run_emits_k_timed_records_per_fixture():
    recs = list(run(fake_client([]), [FIXTURE, {**FIXTURE, "id": "good-02"}], k=3))
    assert [(r["id"], r["sample"]) for r in recs] == [("good-01", i) for i in range(3)] + [
        ("good-02", i) for i in range(3)
    ]
    assert all(r["runner"] == "python" and r["latency_ms"] >= 0 for r in recs)
    assert set(recs[0]["concerns"]) == set(CONCERNS)
    assert all(r["input_tokens"] == 1 and r["output_tokens"] is None for r in recs)
    # input tokens x the published input price; TypeSafe publishes no output price
    assert all(r["cost_usd"] == pytest.approx(1 * INPUT_USD_PER_M / 1_000_000) for r in recs)


def test_cost_is_unknown_not_zero_when_usage_is_not_reported():
    assert cost_usd(None) is None
    assert cost_usd(1_000_000) == pytest.approx(INPUT_USD_PER_M)


def test_run_records_a_blocked_request_and_carries_on():
    def handler(request):
        body = json.loads(request.content)
        if "BLOCKME" in body["state"]:
            return httpx2.Response(403, text="<html>Sorry, you have been blocked</html>")
        answers = {name: {"type": "noul", "noul": 0.25} for name in body["questions"]}
        return httpx2.Response(200, json={"model": body["model"], "usage": {"input_tokens": 1}, "answers": answers})

    client = TypeSafeClient(api_key="test", transport=httpx2.MockTransport(handler))
    blocked = {**FIXTURE, "id": "blocked", "diff": "+BLOCKME\n"}
    recs = list(run(client, [blocked, FIXTURE], k=2))
    # one error record for the blocked fixture: its second repeat is skipped, not re-sent
    assert [(r["id"], r["sample"]) for r in recs] == [("blocked", 0), ("good-01", 0), ("good-01", 1)]
    assert recs[0]["error"] == "TypeSafePermissionDeniedError"
    assert "concerns" not in recs[0]
    assert all("concerns" in r for r in recs[1:])


def test_questions_match_the_baml_version_exactly():
    baml = Path(__file__).parent.parent / "baml_src" / "code_gate.baml"
    # Reason: `baml fmt` wraps long descriptions onto their own line with a trailing comma.
    fields = dict(re.findall(r'(\w+): float @description\(\s*"([^"]+)",?\s*\)', baml.read_text()))
    assert fields == CONCERNS
