"""Recompute scoring and billing offline, then export synthetic provider evidence."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(root, run, output):
    sys.path[:0] = [str(root), str(root/"src")]
    from evals.realworld.harness import code_hashes, dataset, dependencies, loads, reason_schema, score, sha, usage_cost, validator
    import tiktoken
    plan = read(root/"evals/realworld/artifacts/plan.json")
    events = read(run/"events.json")
    summary = read(run/"summary.json")
    workflows, _, gold, _ = dataset()
    assert summary["halt_reason"] is None
    assert summary["plan_sha256"] == sha(plan)
    assert plan["code_sha256"] == code_hashes()
    assert plan["dependency_fingerprint"] == dependencies()
    jobs = {j["id"]: j for j in plan["jobs"]}
    assert len(events) == len(jobs) == 995
    assert len({e["id"] for e in events}) == len(events)
    assert {e["id"] for e in events} == set(jobs)
    log = [json.loads(line) for line in (run/"events.jsonl").read_text(encoding="utf-8").splitlines()]
    starts = [e for e in log if e["status"] == "request_started"]
    results = [e for e in log if e["status"] != "request_started"]
    assert len(starts) == len(events) and results == events
    assert Counter(e["id"] for e in starts) == Counter(jobs.keys())
    encoding = tiktoken.encoding_for_model(plan["config"]["model"])
    export = []
    rescored = 0
    validation_layers = {method:Counter() for method in plan["config"]["methods"]}
    for event in events:
        job = jobs[event["id"]]
        assert event["evidence_kind"] == "openai_live"
        assert event["request_sha256"] == sha(job["request"])
        assert event["status"] == "response_received"
        assert event["schema_acceptance"] == "accepted"
        response = event["response"]
        assert response["model"] == plan["config"]["model"]
        assert response["error"] is None
        assert abs(usage_cost(response["usage"], plan["config"]["pricing"])-event["usage_cost_usd"]) < 1e-12
        if event["phase"] == "intent":
            layer = validation_layers[event["method"]]
            layer["intent_responses"] += 1
            calls = [c for c in response.get("output", []) if c.get("type") == "function_call"]
            if len(calls) == 1:
                layer["exactly_one_tool_call"] += 1
                try:
                    arguments = loads(calls[0]["arguments"])
                except (ValueError, TypeError):
                    pass
                else:
                    layer["json_valid"] += 1
                    action = calls[0].get("name")
                    wire_schema = plan["specs"][job["workflow"]][job["method"]]["schema"] if action == "apply_update" else reason_schema()
                    if action in ("apply_update", "request_clarification", "reject_request") and validator(wire_schema, arguments):
                        layer["wire_schema_valid"] += 1
            recomputed = score(response, job, gold[job["scenario_id"]], workflows[job["workflow"]],
                               plan["specs"][job["workflow"]][job["method"]], encoding)
            assert recomputed == event["score"], event["id"]
            rescored += 1
        # Preserve model text, arguments, token usage and latency; omit opaque provider IDs.
        item = {k:deepcopy(v) for k,v in event.items() if k != "response"}
        item["response_sha256"] = sha(response)
        item["response"] = {k:deepcopy(response.get(k)) for k in
                            ("model", "status", "error", "incomplete_details", "usage", "service_tier")}
        item["response"]["output"] = [
            {k:deepcopy(v) for k,v in value.items() if k not in ("id", "call_id")}
            for value in response.get("output", [])]
        item["returned_tool_strictness"] = [{"name":t.get("name"), "strict":t.get("strict")}
                                            for t in response.get("tools", [])]
        export.append(item)
    total = sum(e["usage_cost_usd"] for e in events)
    assert total <= 5
    assert abs(total-summary["accounted_cost_or_reservation_usd"]) < 1e-12
    output.mkdir(parents=True, exist_ok=False)
    report = {"evidence_kind":"offline_recalculation_of_preserved_live_results", "requests":len(events),
              "rescored_intents":rescored, "score_mismatches":0, "usage_cost_usd":total,
              "plan_sha256":sha(plan), "dataset_manifest_sha256":plan["dataset_manifest_sha256"],
              "raw_events_sha256":hashlib.sha256((run/"events.json").read_bytes()).hexdigest(),
              "published_records_sha256":sha(export),
              "validation_layers":validation_layers,
              "note":"Recomputation verifies consistency, not independent validation of the oracle or scorer. No API calls."}
    for name, value in [("records.json",export),("audit.json",report),("summary.json",summary)]:
        (output/name).write_bytes((json.dumps(value, indent=2, ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "run", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    main(args.root.resolve(), args.run.resolve(), args.output.resolve())
