"""Evaluation-only schema factoring. Wire data and the original codec are unchanged."""
from collections import Counter
from copy import deepcopy
import json

PRESENCE = "Use absent to omit this field; present retains value, including an explicitly allowed null."


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def children(schema):
    for value in schema.get("properties", {}).values():
        yield value
    if isinstance(schema.get("items"), dict):
        yield schema["items"]
    yield from schema.get("anyOf", [])


def compact_schema(source):
    root = deepcopy(source)
    removed = 0
    def strip(node):
        nonlocal removed
        if node.get("description") == PRESENCE:
            node.pop("description")
            removed += 1
        for child in children(node):
            strip(child)
    strip(root)
    counts = Counter()
    def count(node):
        counts[canonical(node)] += 1
        for child in children(node):
            count(child)
    count(root)
    # Factor only repeated complete schema nodes, not arbitrary JSON dictionaries.
    selected = {key for key, n in counts.items() if n >= 2 and len(key) >= 80}
    names = {key: "s" + str(i) for i, key in enumerate(sorted(selected))}
    defs = {}
    def rebuild(node, allow_ref=True):
        key = canonical(node)
        if allow_ref and key in names:
            name = names[key]
            if name not in defs:
                defs[name] = rebuild(node, False)
            return {"$ref": "#/$defs/" + name}
        result = deepcopy(node)
        if "properties" in result:
            result["properties"] = {k: rebuild(v) for k, v in node["properties"].items()}
        if isinstance(node.get("items"), dict):
            result["items"] = rebuild(node["items"])
        if "anyOf" in node:
            result["anyOf"] = [rebuild(v) for v in node["anyOf"]]
        return result
    result = rebuild(root, False)
    if defs:
        result["$defs"] = defs
    if removed:
        result["description"] = PRESENCE
    return result


def expand_local_refs(schema):
    def expand(node):
        if isinstance(node, list):
            return [expand(x) for x in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            assert set(node) == {"$ref"}
            prefix = "#/$defs/"
            assert node["$ref"].startswith(prefix)
            return expand(schema["$defs"][node["$ref"][len(prefix):]])
        return {k: expand(v) for k, v in node.items() if k not in ("$defs", "description", "title")}
    return expand(schema)
