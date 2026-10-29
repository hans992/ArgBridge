"""Reproducible offline comparison of the revised handwritten control and codec.

Counts canonical JSON content tokens, not hidden provider serialization or usage.
No model calls, key loading or expected-outcome generation occurs here.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from argbridge import Compiled, canonical, strict_profile
from bench import manual_wrapper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new path")
    dataset = ROOT / "evals/realworld/dataset"
    workflows = json.loads((dataset / "workflows.json").read_text(encoding="utf-8"))
    scenarios = {
        s["id"]: s for s in json.loads((dataset / "scenarios.json").read_text(encoding="utf-8"))
    }
    expected = json.loads((dataset / "expected.json").read_text(encoding="utf-8"))
    encoding = tiktoken.encoding_for_model("gpt-5.4-mini-2026-03-17")

    def measure(value):
        raw = canonical(value)
        return {"bytes": len(raw.encode("utf-8")), "tokens": len(encoding.encode(raw))}

    rows = []
    for name, workflow in workflows.items():
        source = workflow["schema"]
        codec = Compiled(source)
        manual_schema = manual_wrapper.schema(name, source)
        strict_profile(manual_schema)
        patches = [
            v["patch"] for sid, v in expected.items()
            if v["action"] == "apply_update" and scenarios[sid]["workflow"] == name
        ]
        argument_tokens = {"argbridge": 0, "manual": 0, "original": 0}
        for patch in patches:
            wire = codec.encode(patch)
            manual = manual_wrapper.encode(name, patch)
            assert codec.decode(wire) == patch
            assert manual_wrapper.decode(name, manual, source) == patch
            for arm, value in (("argbridge", wire), ("manual", manual), ("original", patch)):
                argument_tokens[arm] += measure(value)["tokens"]
        rows.append({
            "workflow": name, "exact_reference_roundtrips_each": len(patches),
            "source_schema": measure(source), "argbridge_schema": measure(codec.wire_schema),
            "manual_schema": measure(manual_schema),
            "reference_argument_content_tokens_sum": argument_tokens,
            "argbridge_wire_sha256": hashlib.sha256(canonical(codec.wire_schema).encode()).hexdigest(),
        })
    count = sum(row["exact_reference_roundtrips_each"] for row in rows)
    assert count == 41
    result = {
        "kind": "offline reference roundtrips and content token counts",
        "inference_calls": 0, "live_provider_acceptance_tested": False,
        "model_accuracy_measured": False, "encoding": encoding.name,
        "note": "The expected patches are inputs, not model predictions. Counts are not billed usage. This revised manual arm is not the historical live arm.",
        "exact_reference_roundtrips_each": count, "workflows": rows,
        "source_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [ROOT / "bench/manual_wrapper.py", ROOT / "bench/release_compare.py", ROOT / "src/argbridge/core.py", *sorted(dataset.glob("*.json"))]
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exact_reference_roundtrips_each": count, "workflows": rows}, indent=2))


if __name__ == "__main__":
    main()
