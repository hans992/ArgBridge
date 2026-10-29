"""A bounded, reversible JSON argument codec. No model calls or remote resolution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import NoSuchResource

MAX_BYTES = 1_000_000
MAX_NODES = 20_000
MAX_DATA_DEPTH = 64
ANNOTATIONS = {
    "title",
    "description",
    "default",
    "examples",
    "$comment",
    "deprecated",
    "readOnly",
    "writeOnly",
}
META = ANNOTATIONS | {"$defs", "$schema"}
NUMERIC = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}
OBJECT = {"properties", "required", "additionalProperties"}
ARRAY = {"items", "minItems", "maxItems"}
ALLOWED = META | NUMERIC | OBJECT | ARRAY | {"type", "enum", "const", "anyOf", "oneOf", "$ref"}
TYPES = {"string", "number", "integer", "boolean", "null", "object", "array"}


def pointer(parts) -> str:
    return (
        "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts) if parts else ""
    )


class BridgeError(ValueError):
    def __init__(self, code: str, path: str, detail: str):
        self.code, self.path, self.detail = code, path, detail
        super().__init__(f"{code} at {path or '/'}: {detail}")

    def as_dict(self):
        return {"code": self.code, "path": self.path, "detail": self.detail}


class UnsupportedSchema(BridgeError):
    pass


def _deny_remote(uri):
    raise NoSuchResource(ref=uri)


def canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def check_json(value):
    """Bound work before recursive validators; accept JSON types only, no coercion."""
    stack, count = [(value, 0)], 0
    while stack:
        current, depth = stack.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DATA_DEPTH:
            raise BridgeError("resource_limit", "", "JSON node/depth budget exceeded")
        if type(current) is dict:
            if any(type(k) is not str for k in current):
                raise BridgeError("not_json", "", "Object keys must be strings")
            if count + len(stack) + len(current) > MAX_NODES:
                raise BridgeError("resource_limit", "", "JSON node/depth budget exceeded")
            stack.extend((v, depth + 1) for v in current.values())
        elif type(current) is list:
            if count + len(stack) + len(current) > MAX_NODES:
                raise BridgeError("resource_limit", "", "JSON node/depth budget exceeded")
            stack.extend((v, depth + 1) for v in current)
        elif type(current) not in (str, int, float, bool, type(None)):
            raise BridgeError("not_json", "", "Only JSON values are supported")
        elif type(current) is float and not math.isfinite(current):
            raise BridgeError("not_json", "", "Non-finite numbers are rejected")
    try:
        size = 0
        encoder = json.JSONEncoder(
            ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
        for chunk in encoder.iterencode(value):
            size += len(chunk.encode("utf-8"))
            if size > MAX_BYTES:
                raise BridgeError("resource_limit", "", "JSON byte budget exceeded")
    except BridgeError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BridgeError("not_json", "", "Value is not bounded UTF-8 JSON") from exc


def loads(raw: str):
    if len(raw.encode("utf-8", errors="surrogatepass")) > MAX_BYTES:
        raise BridgeError("resource_limit", "", "JSON byte budget exceeded")

    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise BridgeError("duplicate_json_key", "", "Duplicate object member")
            result[k] = v
        return result

    def constant(_):
        raise BridgeError("not_json", "", "Non-finite numbers are rejected")

    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, BridgeError):
            raise
        raise BridgeError("invalid_json", "", "Malformed or excessively nested JSON") from exc
    check_json(result)
    return result


def closed(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def presence(schema):
    return {
        "anyOf": [
            closed({"state": {"type": "string", "enum": ["absent"]}}),
            closed({"state": {"type": "string", "enum": ["present"]}, "value": schema}),
        ],
        "description": "Use absent to omit this field; present retains value, including an explicitly allowed null.",
    }


def _validate(validator, value, code):
    error = next(validator.iter_errors(value), None)
    if error is not None:
        # Do not copy jsonschema's message: it can contain argument values.
        raise BridgeError(
            code, pointer(error.absolute_path), f"Failed {error.validator} constraint"
        )


def strict_profile(schema):
    """Offline conservative shape check, NOT a live-provider acceptance claim."""
    totals = {"properties": 0, "enum_values": 0, "name_enum_chars": 0, "max_depth": 0}
    allowed = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "anyOf",
        "enum",
        "description",
        "title",
        "minItems",
        "maxItems",
    } | NUMERIC

    def walk(s, depth, path):
        if not isinstance(s, dict) or set(s) - allowed:
            raise UnsupportedSchema(
                "wire_profile", path, "Unsupported wire keyword or boolean schema"
            )
        if "anyOf" in s:
            if set(s) - {"anyOf", "description", "title"}:
                raise UnsupportedSchema(
                    "wire_profile", path, "Compound anyOf siblings are outside this profile"
                )
            for i, branch in enumerate(s["anyOf"]):
                walk(branch, depth, path + "/anyOf/" + str(i))
            return
        typ = s.get("type")
        types = typ if isinstance(typ, list) else [typ]
        if not types or any(t not in TYPES for t in types):
            raise UnsupportedSchema("wire_profile", path, "Explicit type is required")
        if len(types) > 1 and any(t in {"object", "array"} for t in types):
            raise UnsupportedSchema(
                "wire_profile", path, "Container unions require tagged branches"
            )
        if typ in ("object", "array"):
            depth += 1
            totals["max_depth"] = max(totals["max_depth"], depth)
        if depth > 10:
            raise UnsupportedSchema("wire_limit", path, "Wire nesting exceeds ten containers")
        if typ == "object":
            props = s.get("properties", {})
            if s.get("additionalProperties") is not False or set(s.get("required", [])) != set(
                props
            ):
                raise UnsupportedSchema(
                    "wire_profile", path, "Objects must be closed with every property required"
                )
            totals["properties"] += len(props)
            totals["name_enum_chars"] += sum(map(len, props))
            for name, child in props.items():
                walk(child, depth, path + "/properties/" + pointer([name])[1:])
        elif typ == "array":
            if not isinstance(s.get("items"), dict):
                raise UnsupportedSchema("wire_profile", path, "Arrays require a typed item schema")
            walk(s["items"], depth, path + "/items")
        if "enum" in s:
            values = s["enum"]
            totals["enum_values"] += len(values)
            chars = sum(len(v) for v in values if isinstance(v, str))
            totals["name_enum_chars"] += chars
            if len(values) > 250 and chars > 15000:
                raise UnsupportedSchema(
                    "wire_limit", path, "Large string enum exceeds character budget"
                )

    if schema.get("type") != "object" or "anyOf" in schema:
        raise UnsupportedSchema("wire_profile", "", "Wire root must be an object")
    walk(schema, 0, "")
    if (
        totals["properties"] > 5000
        or totals["enum_values"] > 1000
        or totals["name_enum_chars"] > 120000
    ):
        raise UnsupportedSchema("wire_limit", "", "Wire property/enum/character budget exceeded")
    return totals


@dataclass
class _Node:
    kind: str
    wire: dict
    validator: Any
    children: dict = field(default_factory=dict)
    required: frozenset = field(default_factory=frozenset)
    extra: Any = None
    variants: list = field(default_factory=list)

    def encode(self, value):
        if self.kind == "scalar":
            return deepcopy(value)
        if self.kind == "array":
            return [self.extra.encode(v) for v in value]
        if self.kind == "union":
            for i, child in enumerate(self.variants):
                if child.validator.is_valid(value):
                    return {"variant": str(i), "value": child.encode(value)}
            raise BridgeError(
                "internal_union", "", "No branch matches a previously validated input"
            )
        fields = {}
        for k, child in self.children.items():
            if k in self.required:
                fields[k] = child.encode(value[k])
            elif k in value:
                fields[k] = {"state": "present", "value": child.encode(value[k])}
            else:
                fields[k] = {"state": "absent"}
        if self.extra is None:
            return fields
        entries = [
            {"key": k, "value": self.extra.encode(v)}
            for k, v in value.items()
            if k not in self.children
        ]
        return {"fields": fields, "entries": entries} if self.children else {"entries": entries}

    def decode(self, value, path=()):
        if self.kind == "scalar":
            return deepcopy(value)
        if self.kind == "array":
            return [self.extra.decode(v, (*path, i)) for i, v in enumerate(value)]
        if self.kind == "union":
            return self.variants[int(value["variant"])].decode(value["value"], (*path, "value"))
        fields = value if self.extra is None else value.get("fields", {})
        result = {}
        for k, child in self.children.items():
            v = fields[k]
            if k in self.required:
                result[k] = child.decode(v, (*path, k))
            elif v["state"] == "present":
                result[k] = child.decode(v["value"], (*path, k, "value"))
        if self.extra is not None:
            for i, entry in enumerate(value["entries"]):
                key = entry["key"]
                if key in result or key in self.children:
                    raise BridgeError(
                        "duplicate_map_key",
                        pointer((*path, "entries", i, "key")),
                        "Duplicate or declared dictionary key",
                    )
                result[key] = self.extra.decode(entry["value"], (*path, "entries", i, "value"))
        return result


class _Compiler:
    def __init__(self, source, validator):
        self.source, self.validator = source, validator
        self.count = 0

    def fail(self, path, detail):
        raise UnsupportedSchema("unsupported_schema", path, detail)

    def ref(self, ref, path):
        if ref == "#":
            return self.source
        if not ref.startswith("#/") or "%" in ref:
            self.fail(path, "Only literal local JSON Pointer references are supported")
        current = self.source
        for part in ref[2:].split("/"):
            if "~" in part.replace("~0", "").replace("~1", ""):
                self.fail(path, "Invalid JSON Pointer escape")
            token = part.replace("~1", "/").replace("~0", "~")
            try:
                if isinstance(current, list):
                    if (
                        not token.isascii()
                        or not token.isdecimal()
                        or (token.startswith("0") and token != "0")
                    ):
                        self.fail(path, "Invalid array index in JSON Pointer")
                    current = current[int(token)]
                else:
                    current = current[token]
            except (ValueError, KeyError, TypeError, IndexError):
                self.fail(path, "Unresolvable local reference")
        return current

    def compile(self, s, path="", active=(), depth=0):
        self.count += 1
        if self.count > 4000 or depth > 48:
            self.fail(path, "Compilation expansion budget exceeded")
        if not isinstance(s, dict):
            self.fail(path, "Boolean schemas are outside the supported subset")
        bad = set(s) - ALLOWED
        if bad:
            self.fail(path + pointer([sorted(bad)[0]]), "Keyword is outside the supported subset")
        if "$schema" in s and s["$schema"] not in (
            "https://json-schema.org/draft/2020-12/schema",
            "https://json-schema.org/draft/2020-12/schema#",
        ):
            self.fail(path + "/$schema", "Only Draft 2020-12 is supported")
        if "$ref" in s:
            if set(s) - META - {"$ref"}:
                self.fail(path, "Assertion siblings of $ref are not supported")
            ref = s["$ref"]
            if ref in active:
                self.fail(path + "/$ref", "Recursive references are not supported")
            node = self.compile(self.ref(ref, path + "/$ref"), ref[1:], (*active, ref), depth + 1)
            node.wire.update({k: s[k] for k in ("title", "description") if k in s})
            return node
        validator = self.validator.evolve(schema=s)
        if "const" in s and "enum" in s:
            self.fail(path, "Combined const and enum constraints are outside the supported subset")
        union_key = "anyOf" if "anyOf" in s else "oneOf" if "oneOf" in s else None
        if union_key:
            if set(s) - META - {union_key}:
                self.fail(path, "Union assertion siblings are outside the supported subset")
            variants = [
                self.compile(v, path + "/" + union_key + "/" + str(i), active, depth + 1)
                for i, v in enumerate(s[union_key])
            ]
            node = self.union(variants, validator)
            node.wire.update({k: s[k] for k in ("title", "description") if k in s})
            return node
        typ = s.get("type")
        if typ is None and ("enum" in s or "const" in s):
            values = s.get("enum", [s.get("const")])
            if any(type(v) in (dict, list) for v in values):
                self.fail(path, "Container-valued enums are not supported")
            typ = list(dict.fromkeys(self.json_type(v) for v in values))
            typ = typ[0] if len(typ) == 1 else typ
        if typ is None:
            self.fail(path, "Unconstrained or implicit types are not supported")
        types = typ if isinstance(typ, list) else [typ]
        if len(types) > 1 and any(t in ("object", "array") for t in types):
            variants = []
            for t in types:
                branch = {**s, "type": t}
                variants.append(self.compile(branch, path + "/type/" + t, active, depth + 1))
            node = self.union(variants, validator)
            node.wire.update({k: s[k] for k in ("title", "description") if k in s})
            return node
        annotations = {k: s[k] for k in ("title", "description") if k in s}
        if typ == "object":
            if "enum" in s or "const" in s:
                self.fail(path, "Container-valued constraints are not supported")
            props = s.get("properties", {})
            children = {
                k: self.compile(v, path + "/properties" + pointer([k]), active, depth + 1)
                for k, v in props.items()
            }
            required = frozenset(s.get("required", []))
            if required - set(props):
                self.fail(path + "/required", "Required undeclared keys are not supported")
            extra_schema = s.get("additionalProperties", True)
            if extra_schema is True:
                self.fail(
                    path + "/additionalProperties",
                    "Untyped open objects need an explicit value schema",
                )
            fields = closed(
                {
                    k: child.wire if k in required else presence(child.wire)
                    for k, child in children.items()
                }
            )
            extra = None
            wire = fields
            if extra_schema is not False:
                extra = self.compile(
                    extra_schema, path + "/additionalProperties", active, depth + 1
                )
                entries = {
                    "type": "array",
                    "items": closed({"key": {"type": "string"}, "value": extra.wire}),
                }
                wire = closed(
                    {"fields": fields, "entries": entries} if children else {"entries": entries}
                )
            wire.update(annotations)
            return _Node("object", wire, validator, children, required, extra)
        if typ == "array":
            if "enum" in s or "const" in s:
                self.fail(path, "Container-valued constraints are not supported")
            child = self.compile(s.get("items", True), path + "/items", active, depth + 1)
            wire = {"type": "array", "items": child.wire, **annotations}
            wire.update({k: s[k] for k in ("minItems", "maxItems") if k in s})
            return _Node("array", wire, validator, extra=child)
        wire = {"type": typ, **annotations}
        wire.update(
            {k: s[k] for k in NUMERIC if k in s and any(t in ("number", "integer") for t in types)}
        )
        if "enum" in s or "const" in s:
            values = s.get("enum", [s.get("const")])
            if any(type(v) in (dict, list) for v in values):
                self.fail(path, "Container-valued enums are not supported")
            wire["enum"] = deepcopy(values)
        return _Node("scalar", wire, validator)

    @staticmethod
    def json_type(v):
        return {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            type(None): "null",
        }[type(v)]

    @staticmethod
    def union(variants, validator):
        wire = {
            "anyOf": [
                closed({"variant": {"type": "string", "enum": [str(i)]}, "value": v.wire})
                for i, v in enumerate(variants)
            ]
        }
        return _Node("union", wire, validator, variants=variants)


class Compiled:
    """Compile once, then encode or decode bounded JSON values without side effects."""

    def __init__(self, schema: dict[str, Any]):
        check_json(schema)
        self._source = deepcopy(schema)
        try:
            Draft202012Validator.check_schema(self._source)
        except SchemaError as exc:
            raise UnsupportedSchema(
                "invalid_schema", pointer(exc.path), "Invalid Draft 2020-12 schema"
            ) from exc
        self._original = Draft202012Validator(
            self._source, registry=Registry(retrieve=_deny_remote)
        )
        self._node = _Compiler(self._source, self._original).compile(self._source)
        self._wire = closed({"arguments": self._node.wire})
        try:
            check_json(self._wire)
        except BridgeError as exc:
            raise UnsupportedSchema(
                "wire_limit", "", "Expanded wire schema exceeds JSON resource limits"
            ) from exc
        self.profile = strict_profile(self._wire)
        self._wire_validator = Draft202012Validator(self._wire)
        self.fingerprint = hashlib.sha256(canonical(self._source).encode("utf-8")).hexdigest()

    @property
    def wire_schema(self) -> dict[str, Any]:
        """Return an independent copy of the emitted strict tool parameters."""
        return deepcopy(self._wire)

    @property
    def source_schema(self) -> dict[str, Any]:
        return deepcopy(self._source)

    def encode(self, value: Any) -> dict[str, Any]:
        """Validate a source value and encode its exact member presence."""
        check_json(value)
        _validate(self._original, value, "original_invalid")
        result = {"arguments": self._node.encode(value)}
        check_json(result)
        _validate(self._wire_validator, result, "internal_wire_invalid")
        return result

    def decode(self, wire: Any) -> Any:
        """Validate wire data, reconstruct JSON, then enforce the source contract."""
        check_json(wire)
        _validate(self._wire_validator, wire, "wire_invalid")
        result = self._node.decode(wire["arguments"], ("arguments",))
        _validate(self._original, result, "decoded_original_invalid")
        return result

    def guarded_call(self, wire, handler: Callable):
        """Validation boundary only. Does not authenticate, authorize, retry or sandbox a handler."""
        return handler(self.decode(wire))

    def bundle(self):
        result = {
            "format": "argbridge-v1",
            "source_sha256": self.fingerprint,
            "source_schema": self.source_schema,
            "wire_schema": self.wire_schema,
        }
        # A produced bundle must fit the same limits imposed by from_bundle.
        check_json(result)
        return result

    @classmethod
    def from_bundle(cls, bundle):
        check_json(bundle)
        if not isinstance(bundle, dict) or set(bundle) != {
            "format",
            "source_sha256",
            "source_schema",
            "wire_schema",
        }:
            raise BridgeError("invalid_bundle", "", "Unexpected bundle fields")
        if bundle["format"] != "argbridge-v1":
            raise BridgeError("invalid_bundle", "/format", "Unsupported bundle format")
        result = cls(bundle["source_schema"])
        if bundle["source_sha256"] != result.fingerprint or canonical(
            bundle["wire_schema"]
        ) != canonical(result._wire):
            raise BridgeError("invalid_bundle", "", "Bundle hash/schema mismatch")
        return result
