"""Handwritten typed-operation baseline for the four published workflows."""
from copy import deepcopy
from jsonschema import Draft202012Validator

def closed(p):
    return {"type":"object","properties":p,"required":list(p),"additionalProperties":False}

# Deliberately maintained per workflow, independently of ArgBridge's compiler.
FIELDS = {
    "flat": {
        "name": (["name"], {"type":["string","null"]}),
        "enabled": (["enabled"], {"type":"boolean"}),
        "quota": (["quota"], {"type":["integer","null"],"minimum":0}),
    },
    "nested": {
        "nickname": (["settings","nickname"], {"type":["string","null"]}),
        "theme": (["settings","theme"], {"type":"string","enum":["light","dark"]}),
        "timezone": (["settings","timezone"], {"type":["string","null"]}),
        "alerts": (["settings","alerts"], {"type":"boolean"}),
    }
}

def schema(workflow, source):
    if workflow == "ticket":
        return deepcopy(source)
    branches = []
    if workflow in FIELDS:
        for name, (_, value_schema) in FIELDS[workflow].items():
            branches.append(closed({"field":{"type":"string","enum":[name]},"value":value_schema}))
    else:
        branches = [
            closed({"op":{"type":"string","enum":["set_label"]},"key":{"type":"string"},"value":{"type":"string"}}),
            closed({"op":{"type":"string","enum":["remove_label"]},"key":{"type":"string"}}),
            closed({"op":{"type":"string","enum":["clear_labels"]}}),
        ]
    result = closed({"changes":{"type":"array","items":{"anyOf":branches}}})
    result["description"] = "List only explicitly requested changes. Empty changes means no update. Null clears a nullable field."
    return result

def encode(workflow, patch):
    if workflow == "ticket":
        return deepcopy(patch)
    changes = []
    if workflow in FIELDS:
        for name, (path, _) in FIELDS[workflow].items():
            value = patch
            for part in path:
                if not isinstance(value, dict) or part not in value:
                    break
                value = value[part]
            else:
                changes.append({"field":name,"value":deepcopy(value)})
    elif "labels" in patch:
        if patch["labels"] is None:
            changes.append({"op":"clear_labels"})
        else:
            for k,v in patch["labels"].items():
                changes.append({"op":"remove_label","key":k} if v is None else {"op":"set_label","key":k,"value":v})
    return {"changes":changes}

def decode(workflow, wire):
    if workflow == "ticket":
        return deepcopy(wire)
    patch, seen = {}, set()
    for op in wire["changes"]:
        if workflow in FIELDS:
            name = op["field"]
            if name in seen:
                raise ValueError("Duplicate field operation")
            seen.add(name)
            path = FIELDS[workflow][name][0]
            target = patch
            for part in path[:-1]:
                target = target.setdefault(part,{})
            target[path[-1]] = deepcopy(op["value"])
        else:
            if op["op"] == "clear_labels":
                if seen:
                    raise ValueError("Conflicting dictionary operation")
                seen.add(None)
                patch["labels"] = None
            else:
                key = op["key"]
                if None in seen or key in seen:
                    raise ValueError("Duplicate/conflicting dictionary operation")
                seen.add(key)
                patch.setdefault("labels",{})[key] = op["value"] if op["op"]=="set_label" else None
    return patch
