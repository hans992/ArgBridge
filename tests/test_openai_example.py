"""Offline adapter tests; synthetic responses are never provider evidence."""

import importlib.util
import json
from pathlib import Path
import socket

import pytest

from argbridge import BridgeError

spec = importlib.util.spec_from_file_location(
    "openai_example", Path(__file__).parents[1] / "examples/openai_tool.py"
)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*a, **kw):
        pytest.fail("Offline example test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", blocked)


def response(codec, patch, **changes):
    return {
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "name": example.TOOL_NAME,
                "arguments": json.dumps(codec.encode(patch)),
            }
        ],
        **changes,
    }


@pytest.mark.parametrize("patch", [{}, {"name": None}, {"name": "Grace"}, {"enabled": False}])
def test_synthetic_response_preserves_presence(patch):
    codec, request = example.prepare_request("Test instruction")
    assert request["tools"][0]["strict"] is True
    assert request["input"] == "Test instruction"
    assert example.decode_response(codec, response(codec, patch)) == patch


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "incomplete"},
        {"output": []},
        {"output": [{"type": "function_call", "name": "unrelated", "arguments": "{}"}]},
        {
            "output": [
                {"type": "function_call", "name": example.TOOL_NAME, "arguments": '{"x":1,"x":2}'}
            ]
        },
    ],
)
def test_invalid_response_is_not_a_proposal(changes):
    codec, _ = example.prepare_request("Test")
    with pytest.raises(BridgeError):
        example.decode_response(codec, response(codec, {}, **changes))


def test_default_is_offline_and_explicit_paid_consent_required(capsys):
    assert example.main([]) == 0
    assert json.loads(capsys.readouterr().out)["api_calls"] == 0
    with pytest.raises(SystemExit) as exc:
        example.main(["--live"])
    assert exc.value.code == 2


@pytest.mark.evaluation
def test_current_sdk_serializes_example_with_mock_transport():
    import httpx2
    from openai import OpenAI

    codec, request = example.prepare_request("Clear the name")
    observed = []

    def transport(incoming):
        observed.append(json.loads(incoming.content))
        data = response(codec, {"name": None})
        data.update(id="synthetic-response", object="response", created_at=0, model=example.MODEL)
        data["output"][0].update(id="synthetic-call", call_id="synthetic-call", status="completed")
        return httpx2.Response(200, json=data)

    with httpx2.Client(transport=httpx2.MockTransport(transport)) as http:
        with OpenAI(api_key="unit-test", http_client=http, max_retries=0) as client:
            result = client.responses.create(**request).model_dump(mode="json")
    assert len(observed) == 1
    assert observed[0]["tools"][0]["strict"] is True
    assert observed[0]["store"] is False
    assert example.decode_response(codec, result) == {"name": None}
