"""Synthetic, in-memory update demonstration. No model and no external mutation."""

from copy import deepcopy
import json
from pathlib import Path
import sys

from argbridge import BridgeError, Compiled

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": ["string", "null"],
            "description": "Rename, clear with null, or omit to retain.",
        },
        "enabled": {"type": "boolean", "description": "Omit to retain the existing setting."},
    },
    "additionalProperties": False,
}


def merge_patch(target, patch):
    """Small local implementation of RFC 7396 data semantics."""
    if not isinstance(patch, dict):
        return deepcopy(patch)
    result = deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def run():
    compiled = Compiled(SCHEMA)
    before = {"name": "Ada", "enabled": True}
    examples = []
    for label, source in (
        ("keep_name", {"enabled": False}),
        ("clear_name", {"name": None, "enabled": False}),
        ("rename", {"name": "Grace"}),
    ):
        wire = compiled.encode(source)
        decoded = compiled.decode(wire)
        after = compiled.guarded_call(wire, lambda patch: merge_patch(before, patch))
        assert after == merge_patch(before, source)
        examples.append(
            {"intent": label, "source": source, "wire": wire, "decoded": decoded, "after": after}
        )
    assert examples[0]["after"]["name"] == "Ada"
    assert "name" not in examples[1]["after"]
    assert examples[0]["wire"] != examples[1]["wire"]

    # Null-fill has the same transport for these two different intents.
    null_fill_keep = {"name": None, "enabled": False}
    null_fill_clear = {"name": None, "enabled": False}
    assert null_fill_keep == null_fill_clear
    calls = []
    hostile = deepcopy(examples[0]["wire"])
    hostile["arguments"]["name"] = {"state": "present", "value": 123}
    try:
        compiled.guarded_call(hostile, calls.append)
        raise AssertionError("Invalid argument reached handler")
    except BridgeError as exc:
        rejection = exc.as_dict()
    assert not calls
    return {
        "kind": "offline_synthetic_demonstration",
        "before": before,
        "examples": examples,
        "nullable_convention_collision": {
            "keep_name_wire": null_fill_keep,
            "clear_name_wire": null_fill_clear,
            "if_null_is_kept": merge_patch(before, null_fill_keep),
            "consequence": "Keeping null clears a name that was meant to be retained; stripping it would lose a requested clear.",
        },
        "hostile_rejection": rejection,
        "hostile_handler_calls": len(calls),
        "model_calls": 0,
    }


if __name__ == "__main__":
    result = run()
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
