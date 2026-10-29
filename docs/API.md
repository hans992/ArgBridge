# Python API and CLI

## Compile once

`Compiled(schema)` accepts a Draft 2020-12 schema in the [supported subset](SUPPORTED_SCHEMAS.md). It validates the schema, resolves supported local references, builds the wire schema and checks resource limits. It raises `UnsupportedSchema` for unsupported or invalid schemas. JSON resource/type failures can raise the base `BridgeError`.

`codec.source_schema` and `codec.wire_schema` return independent copies. `codec.fingerprint` is the SHA-256 of canonical source-schema JSON; it is not a signature. `codec.profile` describes the local wire shape, not live provider compatibility.

## Encode and decode

```python
from argbridge import Compiled, loads

codec = Compiled({
    "type": "object",
    "properties": {"name": {"type": ["string", "null"]}},
    "additionalProperties": False,
})
wire = codec.encode({"name": None})
assert codec.decode(wire) == {"name": None}
assert codec.encode({}) != wire
```

`encode(value)` first validates ordinary JSON against the source contract, encodes it, checks resource limits and validates the wire result. `decode(wire)` validates the incoming JSON and wire schema, reconstructs the source value, rejects duplicate/colliding map keys and validates the result against the original contract. The result can be a scalar, array or object, depending on the source schema.

For model argument strings, use `codec.decode(loads(arguments))`. `loads` rejects duplicate object members, non-finite numbers, invalid UTF-8 values and excessive resources. Plain `json.loads` has different defaults, including silently collapsing duplicate members.

The codec preserves JSON values and member presence. Your application defines what omission or null means; the codec itself does not clear a database field. Model intent remains a separate concern even after successful validation.

## Bundles

`codec.bundle()` returns the `argbridge-v1` format, source fingerprint and source/wire schemas. It rejects a bundle larger than its reader's budget. `Compiled.from_bundle(bundle)` recompiles the source and verifies the hash and wire schema; it does not execute a serialized transformation plan. Bundle hashes establish consistency, not origin or authorization. Use trusted application schemas.

## Optional handler boundary

`codec.guarded_call(wire, handler)` is equivalent to `handler(codec.decode(wire))`. Validation failure prevents the call; a validated wrong intention can still reach it. Authorization, idempotency, concurrency and transaction handling belong to the application. Handler exceptions propagate. For model integrations, prefer reviewing the decoded proposal before dispatching a mutating handler.

## Errors

`BridgeError` is a `ValueError` with `code`, `path` and `detail`; `as_dict()` returns those fields. `UnsupportedSchema` subclasses `BridgeError`.

- `invalid_schema`, `unsupported_schema`: invalid Draft 2020-12 or unsupported subset.
- `wire_profile`, `wire_limit`: generated wire constraints or resource limits.
- `original_invalid`, `wire_invalid`, `decoded_original_invalid`: validation at the named boundary.
- `duplicate_json_key`, `duplicate_map_key`: ambiguous keys.
- `invalid_json`, `not_json`, `resource_limit`: parsing, JSON type or resource rejection.
- `invalid_bundle`: wrong format, fields, fingerprint or emitted schema.

Paths are JSON Pointers and can contain caller-provided keys. Details omit offending argument values. Internal invariant failures such as `internal_wire_invalid` should be reported with a synthetic reproduction.

## CLI

```sh
argbridge --version
argbridge compile source-schema.json --out bundle.json
argbridge encode bundle.json source-arguments.json --out wire.json
argbridge decode bundle.json wire.json
```

`python -m argbridge` is equivalent. Input is UTF-8 JSON; an initial UTF-8 BOM is accepted. Files are read through a 1,000,000-byte limit. `--out` writes UTF-8 with LF newlines; stdout uses ASCII JSON escapes so Unicode values work on legacy terminals. Success exits 0; expected errors write JSON to stderr and exit 2. Argument-parser usage errors also exit 2. The CLI never uses credentials, opens a network connection or invokes a handler.

`canonical(value)` serializes JSON deterministically for this implementation; it is not RFC 8785 canonicalization. `strict_profile(schema)` is an expert diagnostic for emitted wire schemas, not a general schema validator or a replacement for provider testing.
