"""Handwritten strict control for four fixed contracts, with explicit JSON paths.

This is a new offline comparator. It does not replace the frozen live-run arm.
It is deliberately domain-specific rather than a general schema compiler.
"""

from copy import deepcopy
from jsonschema import Draft202012Validator


def closed(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


FIELDS = {
    "flat": {
        "name": {"type": ["string", "null"]},
        "enabled": {"type": "boolean"},
        "quota": {"type": ["integer", "null"], "minimum": 0},
    },
    "nested": {
        "nickname": {"type": ["string", "null"]},
        "theme": {"type": "string", "enum": ["light", "dark"]},
        "timezone": {"type": ["string", "null"]},
        "alerts": {"type": "boolean"},
    },
}


def schema(workflow, source):
    if workflow == "ticket":
        return deepcopy(source)
    if workflow in FIELDS:
        prefix = "/settings/" if workflow == "nested" else "/"
        branches = [
            closed({"path": {"type": "string", "enum": [prefix + name]}, "value": value})
            for name, value in FIELDS[workflow].items()
        ]
        if workflow == "nested":
            branches.append(
                closed({"path": {"type": "string", "enum": ["/settings"]}, "value": closed({})})
            )
    elif workflow == "labels":
        branches = [
            closed(
                {
                    "op": {"type": "string", "enum": ["set_label"]},
                    "key": {"type": "string"},
                    "value": {"type": ["string", "null"]},
                }
            ),
            closed({"op": {"type": "string", "enum": ["clear_labels", "empty_labels"]}}),
        ]
    else:
        raise ValueError("Unknown workflow")
    result = closed({"changes": {"type": "array", "items": {"anyOf": branches}}})
    result["description"] = (
        "Emit only requested changes. Empty changes omits every field. Paths are exact JSON Pointers in the original contract, "
        "so /settings/timezone updates the nested timezone. A null value removes that nullable field. "
        "set_label merges one labels key; a null value removes that key. clear_labels removes labels; "
        "empty_labels emits labels={} without removing existing keys. /settings with value {} emits an empty settings patch."
    )
    return result


def encode(workflow, patch):
    if workflow == "ticket":
        return deepcopy(patch)
    if workflow == "flat":
        changes = [{"path": "/" + key, "value": deepcopy(value)} for key, value in patch.items()]
    elif workflow == "nested":
        changes = (
            []
            if "settings" not in patch
            else [
                {"path": "/settings/" + key, "value": deepcopy(value)}
                for key, value in patch["settings"].items()
            ]
        )
        if patch.get("settings") == {}:
            changes = [{"path": "/settings", "value": {}}]
    elif workflow == "labels":
        changes = []
        if "labels" in patch:
            labels = patch["labels"]
            changes = (
                [{"op": "clear_labels"}]
                if labels is None
                else [{"op": "empty_labels"}]
                if not labels
                else [
                    {"op": "set_label", "key": key, "value": deepcopy(value)}
                    for key, value in labels.items()
                ]
            )
    else:
        raise ValueError("Unknown workflow")
    return {"changes": changes}


def decode(workflow, wire, source):
    Draft202012Validator(schema(workflow, source)).validate(wire)
    if workflow == "ticket":
        return deepcopy(wire)
    result, seen = {}, set()
    for op in wire["changes"]:
        if workflow in FIELDS:
            path = op["path"]
            if path in seen or path == "/settings" and seen or "/settings" in seen:
                raise ValueError("Duplicate or overlapping path")
            seen.add(path)
            parts = path[1:].split("/")
            target = result
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = deepcopy(op["value"])
        elif op["op"] in ("clear_labels", "empty_labels"):
            if seen:
                raise ValueError("Conflicting labels operations")
            seen.add(None)
            result["labels"] = None if op["op"] == "clear_labels" else {}
        else:
            key = op["key"]
            if None in seen or key in seen:
                raise ValueError("Duplicate or conflicting labels key")
            seen.add(key)
            result.setdefault("labels", {})[key] = deepcopy(op["value"])
    Draft202012Validator(source).validate(result)
    return result
