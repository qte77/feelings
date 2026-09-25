# /// script
# requires-python = ">=3.11"
# ///
"""Score a code-gate eval run: uv run eval/metrics.py <run.jsonl> <fixtures.jsonl>

Export several runs for the results page:
uv run eval/metrics.py --export site/data/results.json eval/fixtures.jsonl "Name=eval/run-x.jsonl" ...
"""

import datetime
import json
import math
import statistics
import sys
from collections import Counter, defaultdict

from concerns import CONCERNS

REJECT_AT = 0.70
CLEAR_BELOW = 0.50
AGREE = 4  # of k=5 samples

BARS = {"auc": 0.80, "agreement": 0.95, "mean_std": 0.02, "false_reject_rate": 0.05, "p95_ms": 3000.0}


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def auc(labels, scores):
    pos = [s for lab, s in zip(labels, scores, strict=True) if lab]
    neg = [s for lab, s in zip(labels, scores, strict=True) if not lab]
    if not pos or not neg:
        return math.nan
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def post_decision(probs):
    if sum(p >= REJECT_AT for p in probs) >= AGREE:
        return "problem"
    if sum(p < CLEAR_BELOW for p in probs) >= AGREE:
        return "clear"
    return "maybe"


def percentile(values, q):
    ranked = sorted(values)
    return ranked[max(math.ceil(q * len(ranked)) - 1, 0)]


def summarize(records, fixtures):
    expect = {f["id"]: f["expect"] for f in fixtures}
    # Reason: group repeats per fixture in sample order; sample 0 is the fast pre-check.
    samples = defaultdict(list)
    errors = [r for r in records if "error" in r]
    if unknown := {r["id"] for r in errors} - expect.keys():
        raise KeyError(f"records for unknown fixtures: {sorted(unknown)}")
    for r in sorted((r for r in records if "error" not in r), key=lambda r: r["sample"]):
        samples[r["id"]].append(r["concerns"])
    ids = list(samples)
    concerns = list(expect[ids[0]])
    is_bad = {fid: any(expect[fid].values()) for fid in ids}
    # Reason: with one sample per fixture, agreement and spread are trivially perfect, not measured.
    repeated = min(len(s) for s in samples.values()) > 1

    per_concern = {}
    pair_stds = []
    for c in concerns:
        labels = [expect[fid][c] for fid in ids]
        probs = [[s[c] for s in samples[fid]] for fid in ids]
        stds = [statistics.pstdev(p) for p in probs]
        pair_stds += stds
        per_concern[c] = {
            "auc_pre": auc(labels, [p[0] for p in probs]),
            "auc_post": auc(labels, [statistics.fmean(p) for p in probs]),
            "agreement": statistics.fmean(len({x >= CLEAR_BELOW for x in p}) == 1 for p in probs) if repeated else None,
            "mean_std": statistics.fmean(stds) if repeated else None,
            "post_maybe_rate": statistics.fmean(post_decision(p) == "maybe" for p in probs) if repeated else None,
        }

    rejected = {fid: any(v >= REJECT_AT for v in samples[fid][0].values()) for fid in ids}
    good = [fid for fid in ids if not is_bad[fid]]
    bad = [fid for fid in ids if is_bad[fid]]
    latencies = [r["latency_ms"] for r in records if r.get("latency_ms") is not None]
    costs = [r["cost_usd"] for r in records if r.get("cost_usd") is not None]
    return {
        "concerns": per_concern,
        "pre": {
            "false_reject_rate": statistics.fmean(rejected[f] for f in good) if good else math.nan,
            "catch_rate": statistics.fmean(rejected[f] for f in bad) if bad else math.nan,
            "n_good": len(good),
            "n_bad": len(bad),
        },
        # Reason: exact repeats across samples may mean a server-side cache, not consistency.
        "zero_std_share": statistics.fmean(s == 0.0 for s in pair_stds) if repeated else None,
        "latency_ms": {"p50": percentile(latencies, 0.50), "p95": percentile(latencies, 0.95)} if latencies else None,
        "cost_usd": {"total": sum(costs), "per_call": statistics.fmean(costs)} if costs else None,
        "errors": error_summary(errors),
    }


def error_summary(errors):
    return {
        "count": len(errors),
        "fixtures": sorted({r["id"] for r in errors}),
        "kinds": dict(Counter(r["error"] for r in errors)),
    }


def verdict(summary):
    checks = {}
    for c, m in summary["concerns"].items():
        checks[f"{c}.auc_post"] = m["auc_post"] >= BARS["auc"]
        if m["agreement"] is not None:
            checks[f"{c}.agreement"] = m["agreement"] >= BARS["agreement"]
            checks[f"{c}.mean_std"] = m["mean_std"] <= BARS["mean_std"]
    checks["pre.false_reject_rate"] = summary["pre"]["false_reject_rate"] <= BARS["false_reject_rate"]
    if summary["latency_ms"]:
        checks["latency.p95"] = summary["latency_ms"]["p95"] <= BARS["p95_ms"]
    return checks


SWEEP = tuple(round(0.5 + 0.05 * i, 2) for i in range(9))  # 0.50 .. 0.90


def sweep(records, fixtures, thresholds=SWEEP):
    """Fast-check trade-off per reject threshold: block if any concern >= t, on the first answer."""
    expect = {f["id"]: f["expect"] for f in fixtures}
    first = {r["id"]: r["concerns"] for r in records if r["sample"] == 0 and "error" not in r}
    good = [fid for fid in first if not any(expect[fid].values())]
    bad = [fid for fid in first if any(expect[fid].values())]
    rows = []
    for t in thresholds:
        rejected = {fid: any(v >= t for v in first[fid].values()) for fid in first}
        rows.append(
            {
                "threshold": t,
                "false_reject_rate": statistics.fmean(rejected[f] for f in good) if good else math.nan,
                "catch_rate": statistics.fmean(rejected[f] for f in bad) if bad else math.nan,
            }
        )
    return rows


def score(records, fixtures):
    summary = summarize(records, fixtures)
    checks = verdict(summary)
    return {"summary": summary, "checks": checks, "go": all(checks.values())}


def _nan_to_none(value):
    # Reason: json.dumps writes bare NaN (e.g. an AUC with one class missing), which JSON.parse rejects.
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _nan_to_none(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nan_to_none(v) for v in value]
    return value


def export(runs, fixtures_path, generated):
    """runs: [(display name, run.jsonl path)], in display order.

    Every runner is scored on the same fixtures: those that all runs answered. A fixture one
    runner never got an answer for (e.g. WAF-blocked) is left out for all of them, so the numbers
    compare like with like. Errors are still reported against each runner's full run.
    """
    fixtures = load_jsonl(fixtures_path)
    known = {f["id"] for f in fixtures}
    loaded = [(name, load_jsonl(path)) for name, path in runs]
    for name, records in loaded:
        if unknown := {r["id"] for r in records} - known:
            raise KeyError(f"{name}: records for unknown fixtures: {sorted(unknown)}")
    common = set.intersection(*({r["id"] for r in records if "error" not in r} for _, records in loaded))
    scored = [f for f in fixtures if f["id"] in common]
    runners = []
    for name, records in loaded:
        kept = [r for r in records if r["id"] in common]
        result = score(kept, scored)
        result["summary"]["errors"] = error_summary([r for r in records if "error" in r])
        runners.append({"name": name, **result, "sweep": sweep(kept, scored)})
    return _nan_to_none(
        {
            "generated": generated,
            "questions": CONCERNS,
            "fixtures_total": len(fixtures),
            "fixtures_scored": len(scored),
            "runners": runners,
        }
    )


def main(argv):
    if argv[0] == "--export":
        # metrics.py --export <out.json> <fixtures.jsonl> <name=run.jsonl>...
        out, fixtures_path, *pairs = argv[1:]
        runs = [tuple(pair.split("=", 1)) for pair in pairs]
        data = export(runs, fixtures_path, generated=datetime.datetime.now(datetime.UTC).date().isoformat())
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, allow_nan=False)
            f.write("\n")
        return
    run_path, fixtures_path = argv[:2]
    print(json.dumps(score(load_jsonl(run_path), load_jsonl(fixtures_path)), indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
