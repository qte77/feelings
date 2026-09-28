import json

import httpx2
from typesafe_sdk import TypeSafeClient

from jev_check import log, main, report, review

MESSAGE = "Add retry to fetch"
DIFF = "+    retry(fetch)\n"


def client(answers=None, status=200):
    """A TypeSafe client whose HTTP goes to a local fake, so no key or spend is needed."""

    def handler(request):
        body = json.loads(request.content)
        if status != 200:
            return httpx2.Response(status, text="<html>Sorry, you have been blocked</html>")
        nouls = {name: {"type": "noul", "noul": (answers or {}).get(name, 0.1)} for name in body["questions"]}
        return httpx2.Response(200, json={"model": body["model"], "usage": {"input_tokens": 1000}, "answers": nouls})

    return TypeSafeClient(api_key="test", transport=httpx2.MockTransport(handler))


def test_review_flags_only_the_questions_at_or_above_the_setting():
    record = review(client({"scope_creep": 0.7, "duplication": 0.69}), MESSAGE, DIFF, at=0.7)
    assert record["flagged"] == ["scope_creep"]
    assert set(record["concerns"]) == {"scope_creep", "single_use_abstraction", "duplication", "weakened_tests"}
    assert record["cost_usd"] > 0 and record["latency_ms"] >= 0


def test_review_turns_an_api_error_into_a_record_instead_of_raising():
    record = review(client(status=403), MESSAGE, DIFF, at=0.7)
    assert record["error"] == "TypeSafePermissionDeniedError"
    assert "concerns" not in record


def test_report_names_flagged_questions_and_says_it_never_blocks():
    text = report(review(client({"weakened_tests": 0.9}), MESSAGE, DIFF, at=0.7), at=0.7)
    assert "weakened_tests" in text and "0.90" in text
    assert "worth a closer look" in text
    assert "never blocks" in text


def test_report_is_quiet_when_nothing_is_flagged_and_explains_a_skip():
    assert "nothing flagged" in report(review(client(), MESSAGE, DIFF, at=0.7), at=0.7)
    assert "skipped" in report({"error": "TypeSafePermissionDeniedError"}, at=0.7)


def test_log_appends_one_json_line_with_an_empty_verdict_for_later_labelling(tmp_path):
    path = tmp_path / "jev-check.jsonl"
    log(path, {"range": "a..b", "flagged": []})
    log(path, {"range": "b..c", "flagged": ["duplication"]})
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [line["range"] for line in lines] == ["a..b", "b..c"]
    assert all(line["verdict"] is None and "time" in line for line in lines)


def test_main_never_fails_even_without_a_key(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("JEV_CHECK_LOG", str(tmp_path / "log.jsonl"))
    assert main(["HEAD~1..HEAD"]) == 0
    assert "skipped" in capsys.readouterr().out
