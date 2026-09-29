import json

from review_queue import (
    added_lines,
    every_setup_flags,
    is_clean,
    main,
    missed_concerns,
    parse_args,
    render,
    render_record,
    select,
    true_concerns,
)

CONCERNS = ["scope_creep", "single_use_abstraction", "duplication", "weakened_tests"]


def fixture(fid, bad_concerns=(), source_repo="qte77/x", source_sha="abcdef01234", message="Fix a thing\n\nbody"):
    return {
        "id": fid,
        "source_repo": source_repo,
        "source_sha": source_sha,
        "message": message,
        "diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,3 @@\n+line one\n+line two\n-old\n",
        "expect": {c: c in bad_concerns for c in CONCERNS},
    }


def first_sample(fid, concerns):
    return {"id": fid, "sample": 0, "concerns": concerns}


# --- true_concerns / is_clean -------------------------------------------------


def test_is_clean_true_when_no_concern_is_labelled():
    assert is_clean(fixture("good-1")) is True
    assert is_clean(fixture("bad-1", ("duplication",))) is False


def test_true_concerns_lists_every_labelled_concern():
    assert true_concerns(fixture("good-1")) == []
    assert true_concerns(fixture("bad-1", ("duplication", "single_use_abstraction"))) == [
        "single_use_abstraction",
        "duplication",
    ]


# --- every_setup_flags (clean side) -------------------------------------------


def test_every_setup_flags_requires_every_answering_setup_to_flag_something():
    answers = [("A", {"duplication": 0.9, "scope_creep": 0.1}), ("B", {"duplication": 0.71, "scope_creep": 0.1})]
    assert every_setup_flags(answers) is True
    answers_one_quiet = [("A", {"duplication": 0.9}), ("B", {"duplication": 0.2})]
    assert every_setup_flags(answers_one_quiet) is False


def test_every_setup_flags_is_false_with_no_answers():
    assert every_setup_flags([]) is False


# --- missed_concerns (flawed side) --------------------------------------------


def test_missed_concerns_only_counts_the_labelled_concern_missed_by_every_setup():
    fx = fixture("bad-1", ("duplication",))
    answers = [("A", {"duplication": 0.5}), ("B", {"duplication": 0.3})]
    assert missed_concerns(fx, answers) == ["duplication"]


def test_missed_concerns_excludes_a_concern_caught_by_any_one_setup():
    fx = fixture("bad-1", ("duplication",))
    answers = [("A", {"duplication": 0.5}), ("B", {"duplication": 0.9})]  # B catches it
    assert missed_concerns(fx, answers) == []


def test_missed_concerns_handles_a_record_with_two_true_concerns_independently():
    # e.g. Agents-eval 812f145 / doc-pipeline-engine ee01aed: a mutation plus single_use_abstraction.
    fx = fixture("bad-2", ("duplication", "single_use_abstraction"))
    answers = [
        ("A", {"duplication": 0.9, "single_use_abstraction": 0.2}),  # catches duplication, misses the other
        ("B", {"duplication": 0.95, "single_use_abstraction": 0.1}),
    ]
    # duplication is caught by every setup; single_use_abstraction is missed by every setup
    assert missed_concerns(fx, answers) == ["single_use_abstraction"]


def test_missed_concerns_is_empty_with_no_answers():
    assert missed_concerns(fixture("bad-1", ("duplication",)), []) == []


# --- added_lines ---------------------------------------------------------------


def test_added_lines_keeps_only_plus_lines_and_drops_the_file_header():
    diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1,3 @@\n+one\n+two\n-old\n+three\n"
    assert added_lines(diff) == ["+one", "+two", "+three"]


def test_added_lines_respects_the_limit():
    diff = "".join(f"+line{i}\n" for i in range(20))
    out = added_lines(diff, limit=15)
    assert len(out) == 15
    assert out[0] == "+line0" and out[-1] == "+line14"


# --- select ----------------------------------------------------------------


def test_select_auto_picks_a_clean_record_every_setup_flags():
    fixtures = [fixture("good-1")]
    runs = [
        ("A", [first_sample("good-1", {"duplication": 0.9})]),
        ("B", [first_sample("good-1", {"duplication": 0.8})]),
    ]
    out = select(fixtures, runs)
    assert len(out) == 1
    assert out[0]["reason"] == "auto"
    assert out[0]["missed"] == []


def test_select_auto_picks_a_flawed_record_every_setup_misses():
    fixtures = [fixture("bad-1", ("duplication",))]
    runs = [("A", [first_sample("bad-1", {"duplication": 0.4})]), ("B", [first_sample("bad-1", {"duplication": 0.1})])]
    out = select(fixtures, runs)
    assert len(out) == 1
    assert out[0]["reason"] == "auto"
    assert out[0]["missed"] == ["duplication"]


def test_select_skips_a_record_that_does_not_qualify_and_is_not_requested():
    fixtures = [fixture("good-1"), fixture("bad-1", ("duplication",))]
    runs = [
        ("A", [first_sample("good-1", {"duplication": 0.1}), first_sample("bad-1", {"duplication": 0.9})]),
    ]
    assert select(fixtures, runs) == []


def test_select_includes_an_also_requested_id_even_if_it_does_not_qualify():
    fixtures = [fixture("good-1")]
    runs = [("A", [first_sample("good-1", {"duplication": 0.1})])]  # A doesn't flag it -> would not auto-qualify
    out = select(fixtures, runs, also=["good-1"])
    assert len(out) == 1
    assert out[0]["reason"] == "requested"


def test_select_ignores_a_setup_that_errored_or_never_answered_the_id():
    fixtures = [fixture("good-1")]
    runs = [
        ("A", [{"id": "good-1", "sample": 0, "error": "Blocked"}]),
        ("B", [first_sample("good-1", {"duplication": 0.9})]),
    ]
    out = select(fixtures, runs)
    assert len(out) == 1
    assert [name for name, _ in out[0]["answers"]] == ["B"]  # A excluded, B alone still "every setup that answered"


def test_select_ignores_samples_after_the_first():
    fixtures = [fixture("good-1")]
    runs = [
        (
            "A",
            [
                first_sample("good-1", {"duplication": 0.1}),  # sample 0: doesn't flag
                {"id": "good-1", "sample": 1, "concerns": {"duplication": 0.99}},
            ],
        )
    ]
    assert select(fixtures, runs) == []  # only sample 0 counted, so it never qualifies


# --- render / render_record --------------------------------------------------


def test_render_record_has_id_source_message_label_scores_diff_and_blank_verdict():
    fx = fixture(
        "bad-1", ("duplication",), source_repo="qte77/x", source_sha="1234567890", message="Do the thing\n\nmore body"
    )
    answers = [("Jev", {"duplication": 0.3, "scope_creep": 0.6})]
    text = render_record(fx, answers, reason="auto", missed=["duplication"])
    assert "`bad-1`" in text
    assert "`qte77/x`@`1234567`" in text  # short sha, first 7 chars
    assert "Do the thing" in text and "more body" not in text  # first line only
    assert "duplication" in text  # label line names the true concern
    assert "questioned: duplication" in text
    assert "Jev: `scope_creep` 0.60" in text  # max concern and its score
    assert "```diff" in text and "+line one" in text and "+line two" in text
    assert "**Owner verdict**" in text


def test_render_record_marks_a_requested_entry_that_did_not_auto_qualify():
    fx = fixture("good-1")
    text = render_record(fx, answers=[], reason="requested", missed=[])
    assert "requested" in text.lower()
    assert "no setup answered" in text.lower()


def test_render_sorts_into_two_sections_with_counts():
    fixtures = [fixture("good-2"), fixture("bad-2", ("duplication",))]
    runs = [("A", [first_sample("good-2", {"duplication": 0.9}), first_sample("bad-2", {"duplication": 0.2})])]
    text = render(fixtures, runs)
    assert "Flawed, missed by every setup (1)" in text
    assert "Clean, flagged by every setup (1)" in text
    assert text.index("bad-2") < text.index("good-2")  # flawed section printed before clean section


def test_render_prefixes_a_dataset_heading_when_given():
    text = render([fixture("good-1")], [("A", [first_sample("good-1", {"duplication": 0.9})])], heading="184 set")
    assert text.startswith("## 184 set")


# --- parse_args ----------------------------------------------------------------


def test_parse_args_reads_positionals_runs_also_and_heading_in_any_order():
    argv = [
        "--also",
        "id-1",
        "eval/fixtures.jsonl",
        "--heading",
        "184 set",
        "out.md",
        "Jev=eval/run-python.jsonl",
        "--also",
        "id-2",
        "Claude=eval/run-claude.jsonl",
    ]
    fixtures_path, out_path, runs, also, heading = parse_args(argv)
    assert fixtures_path == "eval/fixtures.jsonl"
    assert out_path == "out.md"
    assert runs == [("Jev", "eval/run-python.jsonl"), ("Claude", "eval/run-claude.jsonl")]
    assert also == ["id-1", "id-2"]
    assert heading == "184 set"


def test_parse_args_defaults_heading_to_none():
    _, _, _, _, heading = parse_args(["f.jsonl", "o.md", "A=r.jsonl"])
    assert heading is None


# --- main (integration) --------------------------------------------------------


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_main_writes_the_queue_file_from_fixtures_and_named_runs(tmp_path):
    fixtures = write_jsonl(
        tmp_path / "fixtures.jsonl",
        [fixture("good-1"), fixture("bad-1", ("duplication",)), fixture("good-2")],
    )
    run_a = write_jsonl(
        tmp_path / "a.jsonl",
        [
            first_sample("good-1", {"duplication": 0.9}),  # clean, flagged -> auto
            first_sample("bad-1", {"duplication": 0.1}),  # flawed, missed -> auto
            first_sample("good-2", {"duplication": 0.1}),  # neither -> excluded unless requested
        ],
    )
    out = tmp_path / "queue.md"
    main([str(fixtures), str(out), "--heading", "184 set", "--also", "good-2", f"Jev={run_a}"])
    text = out.read_text()
    assert text.startswith("## 184 set")
    assert "good-1" in text and "bad-1" in text and "good-2" in text
    assert "requested" in text.lower()  # good-2 marked as requested, not auto
    assert "**Owner verdict**" in text


def test_select_ignores_run_records_for_ids_outside_the_fixtures_list():
    fixtures = [fixture("good-1")]
    runs = [("A", [first_sample("good-1", {"duplication": 0.9}), first_sample("stray-id", {"duplication": 0.9})])]
    out = select(fixtures, runs)
    assert [item["fixture"]["id"] for item in out] == ["good-1"]
