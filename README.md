# ArgBridge

Experimental, reversible argument transport for strict AI function calling.

ArgBridge compiles a supported subset of JSON Schema into a closed-object, all-fields-required representation. It preserves omitted fields, explicit nulls and typed dictionary contents, and validates decoded arguments against the original contract.

[MIT license](LICENSE) · [Architecture and supported subset](docs/ARCHITECTURE.md) · [Offline benchmark](docs/BENCHMARK.md)

## Status

The deterministic codec and CLI are tested. Real-provider schema acceptance, model intent accuracy and inference costs have not yet been measured. This is not a production-readiness claim.

## Why presence matters

For an update API, leaving a name out can mean "keep the existing name"; sending null can mean "clear it." Replacing both cases with null loses information. ArgBridge uses explicit presence states and reconstructs the original JSON before the application receives it.

Typed dictionaries use key/value entries. Duplicate keys and collisions with declared properties are rejected. A handwritten strict wrapper or a non-strict tool can be a better fit. ArgBridge trades automatic transformation and validation for a larger wire representation.

## Install and run

Python 3.11+ is required; Python 3.12 was tested.

    python -m venv .venv
    .venv/Scripts/python -m pip install -e .
    .venv/Scripts/python examples/demo.py

On macOS/Linux, use .venv/bin/python. Dependency installation downloads public packages; the demo is offline. It keeps, clears and replaces a synthetic name, then rejects invalid arguments without invoking the handler. [Recorded output](bench/results/demo.json).

## Python API

    from argbridge import Compiled

    codec = Compiled({
        "type": "object",
        "properties": {"name": {"type": ["string", "null"]}},
        "additionalProperties": False
    })
    keep = codec.encode({})
    clear = codec.encode({"name": None})
    assert keep != clear
    assert codec.decode(keep) == {}
    assert codec.decode(clear) == {"name": None}

For an eventual model integration, use codec.wire_schema as the tool parameter schema and decode returned arguments before invoking application logic. encode transforms existing JSON; it does not infer natural-language intent.

guarded_call validates the contract. It does not authenticate users, authorize changes, check intent or make side effects safe to retry.

## Command line

    argbridge compile source-schema.json --out bundle.json
    argbridge encode bundle.json source-arguments.json --out wire.json
    argbridge decode bundle.json wire.json

Input is UTF-8 JSON. Duplicate members and non-finite numbers are rejected. Expected failures produce structured stderr errors and exit code 2. Bundles are recompiled and checked on load.

## Offline evidence

- 56 tests passed, including 2,500 generated examples.
- 40/40 workflow round trips were exact.
- 36 invalid inputs and 12 hostile payloads were rejected.
- 87 external assertions passed; 256 were explicitly excluded as unsupported.
- Median encode+decode time: 0.2024 ms; p95: 0.4885 ms, excluding compilation.
- Aggregate schema size: 1,611 to 8,305 UTF-8 bytes, or 5.16×.

These are offline results from a small published corpus, not model-generated results or general JSON Schema conformance. Byte counts are not token counts. The [benchmark](docs/BENCHMARK.md) documents comparator scope and exclusions.

## Reproduce

    python -m pip install -r bench/requirements-lock.txt
    python -m pip install --no-build-isolation --no-deps -e .
    npm --prefix bench/node ci --ignore-scripts --no-audit --no-fund
    node bench/node/compare.mjs
    python bench/run.py
    python -m pytest -q --hypothesis-show-statistics

The benchmark lock preserves the original dependency versions. The core runtime only requires jsonschema. The external JSON Schema suite retains its separate MIT attribution and provenance.

## Scope

Explicit primitive types, scalar enums, typed arrays, closed objects, typed maps, local acyclic references and selected unions/numeric constraints are supported. Patterns, formats, recursive schemas, unconstrained maps and many other keywords fail explicitly.

A valid decoded argument can still represent the wrong user intent. Live model evaluation is required before using this representation for mutating tools.

## Contributing

Provide a minimal schema, source value, expected result and installed versions. Distinguish compilation, encoding, decoding and provider failures. Do not submit API keys, personal data or confidential customer contracts. Preserve benchmark fixtures and distinguish deterministic tests from provider-generated evidence.

MIT licensed. Vendored datasets retain their original notices.

