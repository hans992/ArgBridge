"""Responses API example: offline by default; proposes JSON, never applies an update."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from argbridge import BridgeError, Compiled, loads

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": ["string", "null"],
            "description": "Omit to retain; null requests removal.",
        },
        "enabled": {"type": "boolean", "description": "Omit to retain the current setting."},
    },
    "additionalProperties": False,
}
TOOL_NAME = "propose_contact_update"
MODEL = "gpt-5.4-mini-2026-03-17"


def prepare_request(instruction: str, model: str = MODEL) -> tuple[Compiled, dict[str, Any]]:
    codec = Compiled(SCHEMA)
    request = {
        "model": model,
        "reasoning": {"effort": "none"},
        "temperature": 0,
        "max_output_tokens": 512,
        "store": False,
        "parallel_tool_calls": False,
        "instructions": (
            "Propose only explicitly requested changes. Current state: name=Ada, enabled=true. "
            "In the wire format, absent means DO NOT CHANGE the existing field. "
            "To remove the name, use present with value null. Never infer other changes. "
            "This example only supports clear, unambiguous instructions; the application must review intent."
        ),
        "input": instruction,
        "tools": [
            {
                "type": "function",
                "name": TOOL_NAME,
                "description": "Propose a contact patch for application review.",
                "parameters": codec.wire_schema,
                "strict": True,
            }
        ],
        "tool_choice": {"type": "function", "name": TOOL_NAME},
    }
    return codec, request


def decode_response(codec: Compiled, response: dict[str, Any]) -> Any:
    if response.get("status") != "completed" or response.get("error"):
        raise BridgeError(
            "response_incomplete", "", "Provider response did not complete successfully"
        )
    calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != TOOL_NAME:
        raise BridgeError(
            "unexpected_tool_call", "", "Expected exactly one call to the configured tool"
        )
    arguments = calls[0].get("arguments")
    if not isinstance(arguments, str):
        raise BridgeError("invalid_arguments", "", "Expected a JSON argument string")
    return codec.decode(loads(arguments))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction", default="Clear the name; retain the enabled setting.")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--live", action="store_true", help="Make one billable API request")
    parser.add_argument(
        "--allow-paid-inference", action="store_true", help="Explicit consent for this one request"
    )
    args = parser.parse_args(argv)
    if args.live and not args.allow_paid_inference:
        parser.error("--live requires --allow-paid-inference; API usage is billed separately")
    codec, request = prepare_request(args.instruction, args.model)
    if not args.live:
        print(
            json.dumps(
                {"evidence_kind": "offline_request_preview", "api_calls": 0, "request": request},
                indent=2,
            )
        )
        return 0
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        parser.error("Set your own OPENAI_API_KEY in the environment; do not commit it")
    try:
        from openai import APIError, OpenAI
    except ImportError:
        parser.error("Install the optional dependency with: python -m pip install '.[openai]'")
    try:
        with OpenAI(
            api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=30
        ) as client:
            response = client.responses.create(**request).model_dump(mode="json")
        proposal = decode_response(codec, response)
    except BridgeError as exc:
        print(json.dumps({"error": exc.as_dict()}))
        return 2
    except APIError as exc:
        print(
            json.dumps(
                {"error": {"code": type(exc).__name__, "detail": "API request failed; not retried"}}
            )
        )
        return 2
    print(
        json.dumps(
            {
                "evidence_kind": "live_model_proposal",
                "proposed_patch": proposal,
                "usage": response.get("usage"),
                "applied": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
