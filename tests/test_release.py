"""Release regressions: public boundaries and offline developer workflows."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from argbridge import BridgeError, Compiled, UnsupportedSchema, __version__, canonical
from argbridge.cli import main, read
from argbridge.core import MAX_BYTES


def test_expanded_schema_is_bounded_before_use():
    schema = {
        "$defs": {"v": {"type": "string", "description": "x" * 90000}},
        "type": "object",
        "properties": {str(i): {"$ref": "#/$defs/v"} for i in range(12)},
        "additionalProperties": False,
    }
    with pytest.raises(UnsupportedSchema, match="wire_limit"):
        Compiled(schema)


def test_bundle_cannot_exceed_its_own_reader_budget():
    codec = Compiled({"type": "string", "description": "x" * 600000})
    with pytest.raises(BridgeError, match="resource_limit"):
        codec.bundle()


def test_cli_bounds_read_before_json_parsing(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * (MAX_BYTES + 10))
    with pytest.raises(BridgeError, match="resource_limit"):
        read(path)


def test_cli_reads_bom_and_non_ascii_and_writes_valid_json(tmp_path):
    schema = tmp_path / "schema.json"
    source = tmp_path / "source.json"
    bundle = tmp_path / "bundle.json"
    wire = tmp_path / "wire.json"
    schema.write_bytes(b'\xef\xbb\xbf{"type":"string"}')
    source.write_bytes(json.dumps("雪", ensure_ascii=False).encode("utf-8"))
    cmd = [sys.executable, "-m", "argbridge"]
    subprocess.run([*cmd, "compile", str(schema), "--out", str(bundle)], check=True)
    subprocess.run([*cmd, "encode", str(bundle), str(source), "--out", str(wire)], check=True)
    result = subprocess.run(
        [*cmd, "decode", str(bundle), str(wire)], check=True, capture_output=True
    )
    assert json.loads(result.stdout.decode("ascii")) == "雪"
    assert b"\r\n" not in bundle.read_bytes()


def test_version_and_module_entrypoint():
    result = subprocess.run(
        [sys.executable, "-m", "argbridge", "--version"], check=True, capture_output=True, text=True
    )
    assert result.stdout.strip() == "argbridge " + __version__


def test_external_references_are_refused_without_fetching(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        pytest.fail("Schema compilation attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    with pytest.raises(UnsupportedSchema, match="local JSON Pointer"):
        Compiled({"$ref": "https://example.invalid/secret-schema"})


def test_wide_container_rejected_before_traversal():
    with pytest.raises(BridgeError, match="resource_limit"):
        Compiled({"type": "array", "items": {"type": "integer"}}).encode([0] * 20001)


def test_unsupported_keyword_path_is_a_valid_json_pointer():
    with pytest.raises(UnsupportedSchema) as error:
        Compiled({"type": "string", "x/y~z": True})
    assert error.value.path == "/x~1y~0z"


@pytest.mark.parametrize("target_bytes", [MAX_BYTES - 10, MAX_BYTES])
def test_cli_written_bundle_can_be_read_at_byte_boundary(tmp_path, target_bytes):
    # The default annotation adjusts parity so the exact byte limit is reachable.
    schema = {"type": "string", "description": "", "default": ""}
    overhead = len(canonical(Compiled(schema).bundle()).encode("utf-8"))
    schema["description"] = "x" * ((target_bytes - overhead) // 2)
    expected = Compiled(schema).bundle()
    assert len(canonical(expected).encode("utf-8")) == target_bytes
    source, bundle = tmp_path / "schema.json", tmp_path / "bundle.json"
    source.write_text(canonical(schema), encoding="utf-8")
    assert main(["compile", str(source), "--out", str(bundle)]) == 0
    assert bundle.stat().st_size <= MAX_BYTES
    assert Compiled.from_bundle(read(bundle)).source_schema == schema


def test_cli_ascii_expansion_is_bounded_and_utf8_file_remains_available(tmp_path, capsys):
    codec = Compiled({"type": "string"})
    value = "雪" * 200000
    bundle, source, output = (tmp_path / name for name in ("bundle.json", "input.json", "wire.json"))
    bundle.write_text(canonical(codec.bundle()), encoding="utf-8")
    source.write_text(canonical(value), encoding="utf-8")
    result = main(["encode", str(bundle), str(source)])
    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "resource_limit"
    assert main(["encode", str(bundle), str(source), "--out", str(output)]) == 0
    assert output.stat().st_size <= MAX_BYTES
    assert codec.decode(read(output)) == value
