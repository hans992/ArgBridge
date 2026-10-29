"""Offline analysis of completed, preserved provider responses. Never calls an API."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values, fraction):
    return sorted(values)[min(len(values)-1, int(fraction*len(values)))] if values else None


def metrics(events):
    scores = [e["score"] for e in events if "score" in e]
    correct = sum(s["semantic_correct"] for s in scores)
    cost = sum(e.get("usage_cost_usd", 0) for e in events)
    usages = [e["response"]["usage"] for e in events if e.get("response", {}).get("usage")]
    arguments = [s["generated_argument_tokens"] for s in scores]
    latencies = [e["provider_latency_ms"] for e in events if "provider_latency_ms" in e]
    total_latencies = [e["harness_latency_ms"] for e in events if "harness_latency_ms" in e]
    return {
        "observations": len(events), "scored": len(scores), "correct": correct,
        "semantic_accuracy": correct/len(events) if events else None,
        "validated_through_original_contract": sum(s["structural_valid"] for s in scores),
        "final_state_correct": sum(s["final_state_correct"] for s in scores),
        "wrong_accepted_nonempty_patches": sum(s["unsafe_accepted_mutation"] for s in scores),
        "wrong_nonempty_patch_wrong_final_state": sum(s["unsafe_accepted_mutation"] and not s["final_state_correct"] for s in scores),
        "wrong_nonempty_patch_same_final_state": sum(s["unsafe_accepted_mutation"] and s["final_state_correct"] for s in scores),
        "usage_cost_usd": cost,
        "cost_per_correct_usd": cost/correct if correct and not any("reserved_cost_usd" in e for e in events) else None,
        "input_tokens": sum(u["input_tokens"] for u in usages),
        "cached_input_tokens": sum((u.get("input_tokens_details") or {}).get("cached_tokens", 0) for u in usages),
        "output_tokens": sum(u["output_tokens"] for u in usages),
        "argument_tokens_total": sum(arguments),
        "argument_tokens_mean": statistics.mean(arguments) if arguments else None,
        "argument_tokens_p50": percentile(arguments, .5),
        "argument_tokens_p95": percentile(arguments, .95),
        "provider_latency_p50_ms": percentile(latencies, .5),
        "provider_latency_p95_ms": percentile(latencies, .95),
        "harness_latency_p50_ms": percentile(total_latencies, .5),
        "harness_latency_p95_ms": percentile(total_latencies, .95),
        "failures": dict(Counter(s.get("failure") or "correct" for s in scores)),
    }


def analyze(root, run):
    plan = read(root/"evals/realworld/artifacts/plan.json")
    event_file = run/"events.json" if (run/"events.json").exists() else run/"records.json"
    events = read(event_file)
    summary = read(run/"summary.json")
    scenarios = {s["id"]: s for s in read(root/"evals/realworld/dataset/scenarios.json")}
    expected = read(root/"evals/realworld/dataset/expected.json")
    methods = plan["config"]["methods"]
    intents = [e for e in events if e["phase"] == "intent"]
    probes = [e for e in events if e["phase"] == "schema_probe"]
    by_method = {}
    for method in methods:
        observations = [e for e in intents if e["method"] == method]
        category = {c: metrics([e for e in observations if e["category"] == c])
                    for c in sorted({s["category"] for s in scenarios.values()})}
        workflow = {w: metrics([e for e in observations if e["workflow"] == w])
                    for w in sorted({s["workflow"] for s in scenarios.values()})}
        by_method[method] = {
            **metrics(observations), "target_intents": len(scenarios)*plan["config"]["repetitions"],
            "coverage_adjusted_accuracy": sum(e.get("score", {}).get("semantic_correct", False) for e in observations)/(len(scenarios)*plan["config"]["repetitions"]),
            "categories": category, "workflows": workflow,
            "apply_expected": metrics([e for e in observations if expected[e["scenario_id"]]["action"] == "apply_update"]),
            "nonmutation_expected": metrics([e for e in observations if expected[e["scenario_id"]]["action"] != "apply_update"]),
            "common_non_dictionary": metrics([e for e in observations if e["workflow"] != "labels"]),
        }
    failures = []
    for e in intents:
        if e.get("score", {}).get("semantic_correct"):
            continue
        calls = [{"name": x.get("name"), "arguments": x.get("arguments")}
                 for x in e.get("response", {}).get("output", []) if x.get("type") == "function_call"]
        failures.append({"id": e["id"], "method": e["method"], "category": e["category"],
                         "instruction": scenarios[e["scenario_id"]]["instruction"],
                         "expected": expected[e["scenario_id"]], "score": e.get("score"), "calls": calls})
    consistency = {}
    for method in methods:
        grouped = [[e for e in intents if e["method"] == method and e["scenario_id"] == sid] for sid in scenarios]
        consistency[method] = dict(Counter(
            "unsupported" if not g else "all_correct" if all(e.get("score", {}).get("semantic_correct") for e in g)
            else "all_incorrect" if not any(e.get("score", {}).get("semantic_correct") for e in g) else "mixed"
            for g in grouped))
    transport_fields = ("observations", "usage_cost_usd", "input_tokens", "cached_input_tokens", "output_tokens",
                        "provider_latency_p50_ms", "provider_latency_p95_ms", "harness_latency_p50_ms", "harness_latency_p95_ms")
    return {"evidence_kind": "openai_live_analysis", "plan_sha256": summary["plan_sha256"],
            "halt_reason": summary["halt_reason"], "config": plan["config"],
            "analyzed_events_sha256": hashlib.sha256(event_file.read_bytes()).hexdigest(),
            "analyzed_events_file": event_file.name,
            "model_ids": dict(Counter(e.get("response", {}).get("model") for e in events)),
            "all_requests": {k:v for k,v in metrics(events).items() if k in transport_fields},
            "schema_probes": {k:v for k,v in metrics(probes).items() if k in transport_fields},
            "schema_acceptance": dict(Counter(e.get("schema_acceptance") for e in probes)),
            "methods": by_method, "paired": summary["paired"], "scenario_consistency": consistency,
            "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze(args.root, args.run)
    args.output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"all_requests": result["all_requests"], "schema_acceptance": result["schema_acceptance"],
                      "methods": {k: {f:v[f] for f in ("correct", "observations", "usage_cost_usd", "argument_tokens_mean", "provider_latency_p50_ms", "failures")} for k,v in result["methods"].items()}}, indent=2))
