from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from hypothesis import given, settings, strategies as st
from jsonschema import Draft202012Validator

from argbridge import BridgeError, Compiled, UnsupportedSchema, canonical, loads, strict_profile

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = json.loads((ROOT / "bench/fixtures/workflows.json").read_text())
UNSUPPORTED = json.loads((ROOT / "bench/fixtures/unsupported.json").read_text())
HOSTILE = json.loads((ROOT / "bench/fixtures/hostile.json").read_text())
BY_ID = {w["id"]: w for w in WORKFLOWS}


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda w: w["id"])
def test_frozen_workflow(workflow):
    compiled = Compiled(workflow["schema"])
    assert strict_profile(compiled.wire_schema)
    for value in workflow["valid"]:
        assert Draft202012Validator(workflow["schema"]).is_valid(value)
        wire = compiled.encode(value)
        assert canonical(compiled.decode(wire)) == canonical(value)
    for value in workflow["invalid"]:
        assert not Draft202012Validator(workflow["schema"]).is_valid(value)
        with pytest.raises(BridgeError, match="original_invalid"):
            compiled.encode(value)


@pytest.mark.parametrize("fixture", UNSUPPORTED, ids=lambda w: w["id"])
def test_explicit_abstention(fixture):
    with pytest.raises(UnsupportedSchema) as exc:
        Compiled(fixture["schema"])
    assert exc.value.code and isinstance(exc.value.path, str)


@pytest.mark.parametrize("fixture", HOSTILE, ids=lambda w: w["id"])
def test_hostile_never_calls_handler(fixture):
    c = Compiled(BY_ID[fixture["workflow"]]["schema"])
    calls = []
    with pytest.raises(BridgeError):
        wire = loads(fixture["raw"]) if "raw" in fixture else fixture["wire"]
        c.guarded_call(wire, calls.append)
    assert not calls


def external_groups():
    for file in sorted((ROOT / "bench/external").glob("*.json")):
        if file.name == "SOURCES.json":
            continue
        for i, group in enumerate(json.loads(file.read_text())):
            yield file.name, i, group


def test_external_independent_corpus():
    exercised = excluded = 0
    for file, i, group in external_groups():
        try:
            c = Compiled(group["schema"])
        except UnsupportedSchema:
            excluded += len(group["tests"])
            continue
        for test in group["tests"]:
            exercised += 1
            try:
                wire = c.encode(test["data"])
            except BridgeError as exc:
                assert not test["valid"], (file, i, test, exc.as_dict())
            else:
                assert test["valid"], (file, i, test)
                assert canonical(c.decode(wire)) == canonical(test["data"])
    assert exercised >= 40
    assert excluded > 0  # Scope is deliberately bounded, not a claim of suite-wide conformance.


text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=15)
nullable_text = st.one_of(st.none(), text)


@settings(max_examples=500, deadline=None, derandomize=True)
@given(st.dictionaries(text, st.integers(-10000, 10000), max_size=12))
def test_generated_dynamic_keys(values):
    c = Compiled({"type": "object", "additionalProperties": {"type": "integer"}})
    assert canonical(c.decode(c.encode(values))) == canonical(values)


@settings(max_examples=500, deadline=None, derandomize=True)
@given(st.fixed_dictionaries({"id": text}, optional={"name": nullable_text, "count": st.one_of(st.none(), st.integers(0, 100)), "enabled": st.booleans()}))
def test_generated_presence(values):
    c = Compiled(BY_ID["patch"]["schema"])
    assert canonical(c.decode(c.encode(values))) == canonical(values)


@st.composite
def contracts(draw):
    # Generate schema and data together from independent type definitions, then
    # check them with jsonschema; no compiler internals are used by this oracle.
    kind = draw(st.sampled_from(["string", "integer", "boolean"]))
    scalar = {"type": kind}
    values = {"string": text, "integer": st.integers(-100, 100), "boolean": st.booleans()}
    shape = draw(st.sampled_from(["map", "array", "optional_nullable", "required"]))
    if shape == "map":
        return {"type": "object", "additionalProperties": scalar}, draw(st.dictionaries(text, values[kind], max_size=8))
    if shape == "array":
        return {"type": "array", "items": scalar}, draw(st.lists(values[kind], max_size=8))
    required = shape == "required"
    schema = {"type": "object", "properties": {"x": {"type": [kind, "null"]}},
              "additionalProperties": False, "required": ["x"] if required else []}
    value = {"x": draw(st.one_of(st.none(), values[kind]))} if required or draw(st.booleans()) else {}
    return schema, value


@settings(max_examples=500, deadline=None, derandomize=True)
@given(contracts())
def test_generated_contracts(pair):
    schema, value = pair
    assert Draft202012Validator(schema).is_valid(value)
    c = Compiled(schema)
    assert canonical(c.decode(c.encode(value))) == canonical(value)


json_values = st.recursive(st.one_of(st.none(), st.booleans(), st.integers(), text),
                           lambda children: st.one_of(st.lists(children, max_size=5),
                                                      st.dictionaries(text, children, max_size=5)),
                           max_leaves=20)


@settings(max_examples=500, deadline=None, derandomize=True)
@given(json_values, st.sampled_from(WORKFLOWS))
def test_untrusted_values_must_match_original_or_abstain(value, workflow):
    c = Compiled(workflow["schema"])
    calls = []
    try:
        c.guarded_call(value, calls.append)
    except BridgeError:
        assert not calls
    else:
        assert len(calls) == 1
        assert Draft202012Validator(workflow["schema"]).is_valid(calls[0])


def test_explicit_null_and_omission_are_different_wire_messages():
    c = Compiled(BY_ID["patch"]["schema"])
    assert c.encode({"id": "A"}) != c.encode({"id": "A", "name": None})
    assert c.decode(c.encode({"id": "A", "name": None}))["name"] is None


def test_bundle_integrity_and_defensive_copy():
    source = deepcopy(BY_ID["patch"]["schema"])
    c = Compiled(source)
    source["properties"].clear()
    wire = c.wire_schema
    wire["properties"].clear()
    assert c.decode(c.encode({"id": "A"})) == {"id": "A"}
    bundle = c.bundle()
    assert Compiled.from_bundle(bundle).fingerprint == c.fingerprint
    bundle["wire_schema"]["properties"].clear()
    with pytest.raises(BridgeError, match="invalid_bundle"):
        Compiled.from_bundle(bundle)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1: "x"}, (1, 2), b"bytes"])
def test_non_json_values(bad):
    with pytest.raises(BridgeError):
        Compiled({"type": "number"}).encode(bad)


def test_resource_limits_and_recursive_containers():
    cycle = {}
    cycle["self"] = cycle
    with pytest.raises(BridgeError, match="resource_limit"):
        Compiled({"type": "object", "additionalProperties": {"type": "string"}}).encode(cycle)
    with pytest.raises(BridgeError, match="resource_limit"):
        Compiled({"type": "string"}).encode("x" * 1_000_001)
    schema = {"type": "string"}
    for _ in range(11):
        schema = {"type": "array", "items": schema}
    with pytest.raises(UnsupportedSchema, match="wire_limit"):
        Compiled(schema)


def test_reference_inside_union():
    s = {"$defs": {"label": {"type": "string"}},
         "anyOf": [{"$ref": "#/$defs/label"}, {"type": "integer"}]}
    c = Compiled(s)
    for v in ("", 0, "x", -1):
        assert c.decode(c.encode(v)) == v


def test_errors_do_not_echo_values():
    c = Compiled({"type": "integer"})
    with pytest.raises(BridgeError) as exc:
        c.encode("secret-payload-142")
    assert "secret-payload-142" not in str(exc.value)


def test_special_dictionary_keys_are_data():
    c = Compiled({"type": "object", "additionalProperties": {"type": "integer"}})
    value = {"__proto__": 1, "constructor": 2, "prototype": 3, "": 4, "a/b~c": 5}
    assert c.decode(loads(canonical(c.encode(value)))) == value


def test_cli_end_to_end(tmp_path):
    schema = tmp_path / "source.json"
    bundle = tmp_path / "bundle.json"
    args = tmp_path / "args.json"
    wire = tmp_path / "wire.json"
    schema.write_text(json.dumps(BY_ID["patch"]["schema"]))
    args.write_text('{"id":"A","name":null}')
    base = [sys.executable, "-m", "argbridge.cli"]
    subprocess.run([*base, "compile", str(schema), "--out", str(bundle)], check=True)
    subprocess.run([*base, "encode", str(bundle), str(args), "--out", str(wire)], check=True)
    result = subprocess.run([*base, "decode", str(bundle), str(wire)], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {"id": "A", "name": None}
    args.write_text('{"id":"A","id":"B"}')
    result = subprocess.run([*base, "encode", str(bundle), str(args)], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stderr)["error"]["code"] == "duplicate_json_key"


def test_review_rejects_invalid_array_pointer_and_constraint_combination():
    s = {"$defs": {"choice": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
         "$ref": "#/$defs/choice/anyOf/-1"}
    with pytest.raises(UnsupportedSchema):
        Compiled(s)
    with pytest.raises(UnsupportedSchema):
        Compiled({"type": "string", "enum": ["x", "y"], "const": "x"})


def test_review_preserves_union_and_reference_descriptions():
    c = Compiled({"description": "Select the destination identifier",
                  "anyOf": [{"type": "string"}, {"type": "integer"}]})
    assert c.wire_schema["properties"]["arguments"]["description"] == "Select the destination identifier"
    c = Compiled({"$defs": {"x": {"type": "string"}}, "$ref": "#/$defs/x", "description": "Customer name"})
    assert c.wire_schema["properties"]["arguments"]["description"] == "Customer name"


@settings(max_examples=500, deadline=None, derandomize=True)
@given(st.sampled_from(WORKFLOWS), st.data(), json_values)
def test_mutated_valid_wire_never_bypasses_original_validation(workflow, data, replacement):
    c = Compiled(workflow["schema"])
    source = data.draw(st.sampled_from(workflow["valid"]))
    wire = c.encode(source)
    paths = []

    def collect(value, path):
        paths.append(path)
        if isinstance(value, dict):
            for k, v in value.items():
                collect(v, [*path, k])
        elif isinstance(value, list):
            for i, v in enumerate(value):
                collect(v, [*path, i])
    collect(wire, [])
    path = data.draw(st.sampled_from(paths))
    if not path:
        wire = replacement
    else:
        parent = wire
        for p in path[:-1]:
            parent = parent[p]
        parent[path[-1]] = replacement
    calls = []
    try:
        c.guarded_call(wire, calls.append)
    except BridgeError:
        assert not calls
    else:
        assert len(calls) == 1
        assert Draft202012Validator(workflow["schema"]).is_valid(calls[0])


