import json
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from bench import manual_wrapper as manual
from argbridge import strict_profile

DATA = ROOT / "evals/realworld/dataset"
WORKFLOWS = json.loads((DATA / "workflows.json").read_text(encoding="utf-8"))
SCENARIOS = {s["id"]: s for s in json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))}
GOLD = json.loads((DATA / "expected.json").read_text(encoding="utf-8"))


def test_manual_explicit_paths_preserve_frozen_updates():
    count = 0
    for sid, expected in GOLD.items():
        if expected["action"] != "apply_update":
            continue
        workflow = SCENARIOS[sid]["workflow"]
        source = WORKFLOWS[workflow]["schema"]
        schema = manual.schema(workflow, source)
        assert strict_profile(schema)
        wire = manual.encode(workflow, expected["patch"])
        assert Draft202012Validator(schema).is_valid(wire)
        assert manual.decode(workflow, wire, source) == expected["patch"]
        count += 1
    assert count == 41


@pytest.mark.parametrize(
    "workflow,patch",
    [
        ("nested", {"settings": {}}),
        ("labels", {"labels": {}}),
        ("nested", {}),
        ("labels", {}),
        ("labels", {"labels": None}),
        ("labels", {"labels": {"": None, "a/b": "雪"}}),
    ],
)
def test_empty_objects_and_dynamic_keys(workflow, patch):
    assert (
        manual.decode(workflow, manual.encode(workflow, patch), WORKFLOWS[workflow]["schema"])
        == patch
    )


def test_duplicate_and_overlapping_operations_fail():
    source = WORKFLOWS["nested"]["schema"]
    empty = {"path": "/settings", "value": {}}
    field = {"path": "/settings/timezone", "value": None}
    for changes in ([field, field], [empty, field], [field, empty]):
        with pytest.raises(ValueError):
            manual.decode("nested", {"changes": changes}, source)
