"""Reproducible offline evaluation. No inference, customer data, or network I/O."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from argbridge import BridgeError, Compiled, UnsupportedSchema, canonical, loads, strict_profile
from jsonschema import Draft202012Validator
from openai.lib._pydantic import _ensure_strict_json_schema

OUT = ROOT / "bench/results"
OUT.mkdir(exist_ok=True)
fixtures = json.loads((ROOT / "bench/fixtures/workflows.json").read_text())
by_id = {f["id"]: f for f in fixtures}


def size(value):
    return len(canonical(value).encode("utf-8"))


def quantile(values, p):
    ordered = sorted(values)
    return ordered[max(0, __import__("math").ceil(p * len(ordered)) - 1)]


def summary(values):
    return {"n": len(values), "median_ms": round(statistics.median(values), 4),
            "p95_ms": round(quantile(values, .95), 4), "max_ms": round(max(values), 4)}


def normalize(source, nullable=False):
    """Own deterministic baseline, not attributed to a third-party runtime."""
    s = deepcopy(source)
    if isinstance(s, dict):
        for defs in ("$defs", "definitions"):
            if defs in s:
                s[defs] = {k: normalize(v, nullable) for k, v in s[defs].items()}
        if "properties" in s or s.get("type") == "object" or isinstance(s.get("type"), list) and "object" in s["type"]:
            required = set(s.get("required", []))
            props = {}
            for k, value in s.get("properties", {}).items():
                child = normalize(value, nullable)
                if nullable and k not in required:
                    child = {"anyOf": [child, {"type": "null"}]}
                props[k] = child
            s.update(properties=props, required=list(props), additionalProperties=False)
        if isinstance(s.get("items"), dict):
            s["items"] = normalize(s["items"], nullable)
        for key in ("anyOf", "oneOf", "allOf"):
            if key in s:
                s[key] = [normalize(v, nullable) for v in s[key]]
    return s


def nullable_encode(s, value):
    if isinstance(value, dict) and (s.get("type") == "object" or "properties" in s):
        result = deepcopy(value)
        for k, child in s.get("properties", {}).items():
            if k in value:
                result[k] = nullable_encode(child, value[k])
            elif k not in s.get("required", []):
                result[k] = None
        return result
    if isinstance(value, list) and isinstance(s.get("items"), dict):
        return [nullable_encode(s["items"], v) for v in value]
    return deepcopy(value)


def nullable_decode(s, value, root_validator):
    if isinstance(value, dict) and (s.get("type") == "object" or "properties" in s):
        result = deepcopy(value)
        for k, child in s.get("properties", {}).items():
            if k not in value:
                continue
            introduced_null = value[k] is None and k not in s.get("required", []) and not root_validator.evolve(schema=child).is_valid(None)
            if introduced_null:
                result.pop(k)
            else:
                result[k] = nullable_decode(child, value[k], root_validator)
        return result
    if isinstance(value, list) and isinstance(s.get("items"), dict):
        return [nullable_decode(s["items"], v, root_validator) for v in value]
    return deepcopy(value)


results = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                    "jsonschema": version("jsonschema"), "openai": version("openai"),
                    "hypothesis": version("hypothesis"), "pytest": version("pytest")},
    "scope": {"inference_calls": 0, "inference_cost": 0, "live_provider_acceptance_tested": False,
              "generation_accuracy_measured": False, "token_cost_measured": False,
              "commercial_validation": "unverified"},
    "workflows": [], "baseline_roundtrips": [], "external": [], "hostile": [], "unsupported": []
}
all_latencies = []
compile_latencies = []
codec_valid = codec_invalid_rejected = 0

for f in fixtures:
    compile_start = perf_counter_ns()
    c = Compiled(f["schema"])
    compile_latencies.append((perf_counter_ns() - compile_start) / 1e6)
    latencies, payloads = [], []
    for v in f["valid"]:
        wire = c.encode(v)
        assert canonical(c.decode(wire)) == canonical(v), f["id"]
        codec_valid += 1
        payloads.append({"source_bytes": size(v), "wire_bytes": size(wire)})
        # Warm before measuring, compile excluded; still includes both source and wire validation.
        for _ in range(3):
            c.decode(c.encode(v))
        for _ in range(30):
            start = perf_counter_ns()
            restored = c.decode(c.encode(v))
            latencies.append((perf_counter_ns() - start) / 1e6)
            assert canonical(restored) == canonical(v)
    for v in f["invalid"]:
        try:
            c.encode(v)
            raise AssertionError(f"Invalid source accepted: {f['id']}")
        except BridgeError as exc:
            assert exc.code == "original_invalid", exc.as_dict()
            codec_invalid_rejected += 1
    all_latencies.extend(latencies)
    results["workflows"].append({"id": f["id"], "valid_exact": len(f["valid"]),
                                "invalid_rejected": len(f["invalid"]),
                                "source_schema_bytes": size(f["schema"]),
                                "wire_schema_bytes": size(c.wire_schema),
                                "wire_profile": c.profile, "payloads": payloads,
                                "encode_decode": summary(latencies)})
    for name, nullable in (("require_and_close_identity", False), ("nullable_fill_schema_aware_strip", True)):
        transformed = normalize(f["schema"], nullable)
        wire_validator = Draft202012Validator(transformed)
        original = Draft202012Validator(f["schema"])
        outcomes = Counter()
        for value in f["valid"]:
            wire = nullable_encode(f["schema"], value) if nullable else deepcopy(value)
            if not wire_validator.is_valid(wire):
                outcomes["wire_rejected"] += 1
                continue
            restored = nullable_decode(f["schema"], wire, original) if nullable else wire
            if canonical(restored) != canonical(value):
                outcomes["semantic_loss"] += 1
            else:
                outcomes["exact"] += 1
        results["baseline_roundtrips"].append({"workflow": f["id"], "method": name,
                                              "total": len(f["valid"]), **dict(outcomes)})

for file in sorted((ROOT / "bench/external").glob("*.json")):
    if file.name == "SOURCES.json":
        continue
    for index, group in enumerate(json.loads(file.read_text())):
        row = {"file": file.name, "group_index": index, "description": group["description"],
               "assertions": len(group["tests"])}
        try:
            c = Compiled(group["schema"])
        except UnsupportedSchema as exc:
            row.update(status="unsupported", reason=exc.as_dict())
        else:
            row.update(status="exercised", assertions_passed=0, failures=[])
            for test in group["tests"]:
                try:
                    wire = c.encode(test["data"])
                    actual_valid = True
                    exact = canonical(c.decode(wire)) == canonical(test["data"])
                except BridgeError as exc:
                    actual_valid, exact = False, True
                if actual_valid == test["valid"] and exact:
                    row["assertions_passed"] += 1
                else:
                    row["failures"].append({"description": test["description"],
                                            "expected_valid": test["valid"], "actual_valid": actual_valid})
        results["external"].append(row)

for f in json.loads((ROOT / "bench/fixtures/unsupported.json").read_text()):
    try:
        Compiled(f["schema"])
        raise AssertionError("Unsupported schema unexpectedly accepted: " + f["id"])
    except UnsupportedSchema as exc:
        results["unsupported"].append({"id": f["id"], "reason": exc.as_dict()})

for f in json.loads((ROOT / "bench/fixtures/hostile.json").read_text()):
    calls = []
    c = Compiled(by_id[f["workflow"]]["schema"])
    try:
        wire = loads(f["raw"]) if "raw" in f else f["wire"]
        c.guarded_call(wire, calls.append)
        raise AssertionError("Hostile payload accepted: " + f["id"])
    except BridgeError as exc:
        assert calls == []
        results["hostile"].append({"id": f["id"], "rejected": True, "handler_calls": 0,
                                   "reason": exc.as_dict()})

# Execute the actual installed SDK helper, preserve its output, and make only
# schema-level observations. It does not claim to be an arbitrary-schema codec.
sdk = []
for f in fixtures:
    try:
        s = deepcopy(f["schema"])
        emitted = _ensure_strict_json_schema(s, path=(), root=s)
        sdk.append({"id": f["id"], "schema": emitted})
    except Exception as exc:
        sdk.append({"id": f["id"], "error": type(exc).__name__ + ": " + str(exc)})
(OUT / "openai-sdk.json").write_text(json.dumps({
    "comparator": "openai.lib._pydantic._ensure_strict_json_schema",
    "version": version("openai"), "private_helper": True,
    "note": "Direct schema helper invocation. Not a benchmark of the full SDK or a promise that its public API accepts arbitrary JSON Schema.",
    "results": sdk}, indent=2) + "\n", encoding="utf-8")

mastra = json.loads((OUT / "mastra.json").read_text())
comparison = []
for name, rows in (("openai_sdk_helper", sdk), ("mastra_schema_layer", mastra["results"])):
    schemas = {r["id"]: r.get("schema") for r in rows}
    for workflow in ("patch", "neutral", "typed_map", "mixed_map", "required_null"):
        s = schemas[workflow]
        if not s:
            comparison.append({"method": name, "workflow": workflow, "error": True})
            continue
        v = Draft202012Validator(s)
        row = {"method": name, "workflow": workflow,
               "original_valid_messages_accepted_without_transport": sum(v.is_valid(x) for x in by_id[workflow]["valid"]),
               "original_valid_messages_total": len(by_id[workflow]["valid"]),
               "source_invalid_messages_accepted_by_emitted_schema_only": sum(v.is_valid(x) for x in by_id[workflow]["invalid"]),
               "note": "Schema observations only; a downstream source validator may reject relaxed constraints."}
        if workflow == "patch":
            filled = {"id": "A", "name": None, "count": None, "enabled": None}
            row.update(all_optional_null_wire_accepted=v.is_valid(filled),
                       optional_nullable_name_is_required="name" in s.get("required", []),
                       explicit_null_name_allowed=Draft202012Validator(s["properties"]["name"]).is_valid(None),
                       omitted_nullable_name_allowed=v.is_valid({"id": "A", "count": None, "enabled": None}))
        if workflow == "typed_map":
            row.update(nonempty_dictionary_allowed=v.is_valid({"revenue": 1.25}),
                       additional_properties=s.get("additionalProperties"),
                       closed_object_contract=s.get("additionalProperties") is False)
        comparison.append(row)
results["installed_oss_schema_observations"] = comparison

ext = results["external"]
exercised = [r for r in ext if r["status"] == "exercised"]
external_n = sum(r["assertions"] for r in exercised)
failures = sum(len(r["failures"]) for r in exercised)
results["totals"] = {
    "local_valid_exact": codec_valid, "local_invalid_rejected": codec_invalid_rejected,
    "hostile_rejected": len(results["hostile"]), "hostile_handler_calls": 0,
    "unsupported_fixture_schemas": len(results["unsupported"]),
    "external_groups_total": len(ext), "external_groups_exercised": len(exercised),
    "external_assertions_total": sum(r["assertions"] for r in ext),
    "external_assertions_exercised": external_n, "external_assertion_failures": failures,
    "external_assertions_excluded": sum(r["assertions"] for r in ext if r["status"] == "unsupported"),
    "compile": summary(compile_latencies), "encode_decode": summary(all_latencies),
}
results["gate_checks"] = {
    "external_minimum_40": external_n >= 40,
    "external_zero_disagreements": failures == 0,
    "local_roundtrips_and_rejections": True,
    "hostile_zero_handler_calls": True,
    "wire_profiles_pass": True,
    "latency_median_below_20ms": statistics.median(all_latencies) < 20,
    "latency_p95_below_50ms": quantile(all_latencies, .95) < 50,
    "presence_and_map_advantage_over_baselines": all(
        r.get("exact", 0) < r["total"] for r in results["baseline_roundtrips"]
        if r["workflow"] in ("patch", "typed_map")
    ),
    "neutral_baselines_equal": all(
        r.get("exact", 0) == r["total"] for r in results["baseline_roundtrips"]
        if r["workflow"] in ("neutral", "required_null")
    ),
}
assert all(results["gate_checks"].values()), results["gate_checks"]
results["input_hashes"] = {
    str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ("bench/fixtures", "bench/external") for p in sorted((ROOT / folder).glob("*")) if p.is_file()
}
(OUT / "benchmark.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"totals": results["totals"], "gate_checks": results["gate_checks"]}, indent=2))

