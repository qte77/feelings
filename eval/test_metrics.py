import math
import statistics

import pytest

from metrics import auc, post_decision, summarize, verdict

CONCERNS = ["scope_creep", "single_use_abstraction", "duplication", "weakened_tests"]


def fixture(fid, bad_concern=None):
    return {"id": fid, "expect": {c: c == bad_concern for c in CONCERNS}}


def records(fid, samples):
    """samples: one dict of concern -> probability per repeat."""
    return [
        {"id": fid, "sample": i, "latency_ms": 100.0 + i, "concerns": {c: s.get(c, 0.1) for c in CONCERNS}}
        for i, s in enumerate(samples)
    ]


def test_auc_perfect_inverted_and_tied():
    assert auc([False, False, True, True], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([False, False, True, True], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert auc([False, True], [0.5, 0.5]) == 0.5


def test_auc_is_nan_when_one_class_is_missing():
    assert math.isnan(auc([False, False], [0.1, 0.2]))


@pytest.mark.parametrize(
    ("probs", "expected"),
    [
        ([0.9, 0.8, 0.75, 0.7, 0.2], "problem"),  # 4 of 5 at or above 0.70
        ([0.1, 0.2, 0.3, 0.4, 0.9], "clear"),  # 4 of 5 below 0.50
        ([0.6, 0.6, 0.9, 0.1, 0.55], "maybe"),  # neither side reaches 4
    ],
)
def test_post_decision_needs_four_of_five_on_one_side(probs, expected):
    assert post_decision(probs) == expected


def test_pre_check_uses_first_sample_and_rejects_only_when_confident():
    fixtures = [fixture("good-a"), fixture("good-b"), fixture("bad-a", "duplication"), fixture("bad-b", "scope_creep")]
    recs = (
        records("good-a", [{}, {"duplication": 0.99}])  # later samples must not matter for pre
        + records("good-b", [{"scope_creep": 0.72}, {}])  # a false reject
        + records("bad-a", [{"duplication": 0.9}, {}])  # caught
        + records("bad-b", [{"scope_creep": 0.65}, {}])  # uncertain -> not rejected
    )
    pre = summarize(recs, fixtures)["pre"]
    assert pre["false_reject_rate"] == 0.5
    assert pre["catch_rate"] == 0.5


def test_per_concern_agreement_std_and_zero_std_share():
    fixtures = [fixture("good"), fixture("bad", "weakened_tests")]
    recs = records("good", [{"weakened_tests": 0.1}] * 5) + records(
        "bad", [{"weakened_tests": p} for p in (0.9, 0.8, 0.4, 0.9, 0.9)]
    )
    s = summarize(recs, fixtures)
    wt = s["concerns"]["weakened_tests"]
    assert wt["auc_pre"] == 1.0
    assert wt["auc_post"] == 1.0
    assert wt["agreement"] == 0.5  # "good" unanimous, "bad" split across 0.5
    assert wt["mean_std"] == pytest.approx(statistics.pstdev([0.9, 0.8, 0.4, 0.9, 0.9]) / 2)
    # every (fixture, concern) pair except weakened_tests on "bad" repeats exactly
    assert s["zero_std_share"] == pytest.approx(7 / 8)


def test_latency_percentiles():
    fixtures = [fixture("good")]
    recs = records("good", [{}] * 5)  # latencies 100..104
    lat = summarize(recs, fixtures)["latency_ms"]
    assert lat["p50"] == 102.0
    assert lat["p95"] == 104.0


def test_single_sample_runs_report_repeatability_as_not_measured():
    fixtures = [fixture("good"), fixture("bad", "duplication")]
    recs = records("good", [{}]) + records("bad", [{"duplication": 0.9}])
    s = summarize(recs, fixtures)
    assert s["concerns"]["duplication"]["auc_post"] == 1.0
    assert s["concerns"]["duplication"]["agreement"] is None
    assert s["concerns"]["duplication"]["mean_std"] is None
    assert s["concerns"]["duplication"]["post_maybe_rate"] is None  # 4-of-5 needs repeats
    assert s["zero_std_share"] is None
    checks = verdict(s)
    assert not any(name.endswith((".agreement", ".mean_std")) for name in checks)


def test_cost_is_summed_when_runners_report_it():
    fixtures = [fixture("good")]
    recs = [{**r, "cost_usd": 0.02} for r in records("good", [{}, {}])]
    assert summarize(recs, fixtures)["cost_usd"] == {"total": pytest.approx(0.04), "per_call": pytest.approx(0.02)}
    assert summarize(records("good", [{}]), fixtures)["cost_usd"] is None


def test_errored_records_are_counted_and_left_out_of_scoring():
    fixtures = [fixture("good"), fixture("bad", "duplication"), fixture("blocked")]
    recs = (
        records("good", [{}])
        + records("bad", [{"duplication": 0.9}])
        + [{"id": "blocked", "sample": 0, "error": "TypeSafePermissionDeniedError"}]
    )
    s = summarize(recs, fixtures)
    assert s["errors"] == {"count": 1, "fixtures": ["blocked"], "kinds": {"TypeSafePermissionDeniedError": 1}}
    assert s["concerns"]["duplication"]["auc_post"] == 1.0
    assert s["pre"]["false_reject_rate"] == 0.0  # "blocked" is not counted as a good fixture


def test_records_for_unknown_fixture_fail_loudly():
    with pytest.raises(KeyError):
        summarize(records("nope", [{}]), [fixture("good")])
