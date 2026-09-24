import json
import subprocess
import threading
import time

import pytest

import claude_gate
from claude_gate import SCHEMA, build_command, check, run
from concerns import CONCERNS

FIXTURE = {"id": "good-01", "message": "Add retry to fetch", "diff": "+    retry(fetch)\n"}


def fake_cli(seen, answer=None, **extra):
    """Stands in for `claude -p`: records the argv, returns a result like the real CLI."""

    def call(argv):
        seen.append(argv)
        structured = answer if answer is not None else {name: 0.25 for name in CONCERNS}
        return json.dumps({"type": "result", "is_error": False, "structured_output": structured, **extra})

    return call


def test_command_uses_the_logged_in_session_with_no_tools_and_no_workspace_config():
    argv = build_command("the state", model="haiku")
    assert argv[:2] == ["claude", "-p"]
    for flag in ["--safe-mode", "--no-session-persistence"]:
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--bare" not in argv  # --bare ignores OAuth, so it would need an API key
    assert json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA


def test_command_skips_user_settings_so_no_advisor_model_or_effort_level_joins_in():
    argv = build_command("the state", model="haiku")
    assert argv[argv.index("--setting-sources") + 1] == "project,local"


def test_command_turns_thinking_off_for_speed():
    argv = build_command("the state", model="haiku")
    assert json.loads(argv[argv.index("--settings") + 1]) == {"alwaysThinkingEnabled": False}


def test_cli_gives_claude_empty_stdin_so_the_fixtures_file_never_leaks_into_the_prompt(monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

    monkeypatch.setattr(claude_gate.subprocess, "run", fake_run)
    claude_gate.cli(["claude", "-p", "x"])
    assert seen["stdin"] is subprocess.DEVNULL


def test_prompt_asks_the_same_four_questions_about_the_state():
    prompt = build_command("the state", model="haiku")[2]
    assert "the state" in prompt
    for name, question in CONCERNS.items():
        assert f"{name}: {question}" in prompt


def test_schema_requires_one_probability_per_concern():
    assert set(SCHEMA["required"]) == set(CONCERNS)
    assert all(SCHEMA["properties"][c] == {"type": "number", "minimum": 0, "maximum": 1} for c in CONCERNS)
    assert SCHEMA["additionalProperties"] is False


def test_check_returns_the_answer_the_model_that_answered_and_the_cost():
    answer = {name: 0.9 for name in CONCERNS}
    call = fake_cli([], answer, total_cost_usd=0.02, modelUsage={"claude-haiku-4-5-20251001": {}})
    assert check(call, "state", model="haiku") == {
        "concerns": answer,
        "cost_usd": 0.02,
        "model_used": "claude-haiku-4-5-20251001",
    }


def test_check_fails_loudly_on_a_cli_error():
    with pytest.raises(RuntimeError, match="claude -p failed"):
        check(fake_cli([], is_error=True), "state", model="haiku")


def test_run_emits_k_timed_records_labelled_with_the_model():
    recs = list(run(fake_cli([]), [FIXTURE], k=2, model="haiku"))
    assert [(r["id"], r["sample"]) for r in recs] == [("good-01", 0), ("good-01", 1)]
    assert all(r["runner"] == "claude-haiku" and r["latency_ms"] >= 0 for r in recs)
    assert set(recs[0]) >= {"concerns", "cost_usd", "model_used"}


def test_run_calls_in_parallel_up_to_the_worker_limit():
    lock, active, peak = threading.Lock(), [0], [0]
    inner = fake_cli([])

    def slow_call(argv):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return inner(argv)

    fixtures = [{**FIXTURE, "id": f"f{i}"} for i in range(4)]
    recs = list(run(slow_call, fixtures, k=2, model="haiku", workers=3))
    assert sorted((r["id"], r["sample"]) for r in recs) == [(f"f{i}", s) for i in range(4) for s in range(2)]
    assert peak[0] == 3
