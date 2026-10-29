# Supported JSON Schema subset

ArgBridge deliberately refuses schemas it cannot transport. This is a codec for a bounded subset of Draft 2020-12, not a general JSON Schema validator or a universal OpenAPI/Pydantic converter.

## Supported shapes

- Explicit primitive types: string, integer, number, boolean and null; primitive type unions.
- Scalar `enum`/`const`, including inferred scalar types when `type` is absent. Combining `enum` and `const` is refused.
- Closed objects with declared properties and required keys. Optional nullable properties retain omission, explicit null and concrete values separately.
- Typed maps using a schema-valued `additionalProperties`, including mixed declared/dynamic properties. Dictionary keys are transported as entries; duplicate keys and collisions with declared properties are rejected.
- Homogeneous typed arrays with `items`, `minItems` and `maxItems`.
- `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` and `multipleOf`. Ordinary JSON Schema rules still apply when a keyword is inapplicable to a type.
- `anyOf`/`oneOf` without assertion siblings and unions containing containers, represented by tagged branches. Original validation enforces `oneOf` exclusivity after decoding.
- Local acyclic JSON Pointer references and `$defs`. Assertion siblings of `$ref` are refused. Titles/descriptions are carried into supported wire nodes; defaults never insert values.

## Explicit refusals

Boolean schemas; unconstrained/implicit types except scalar enum inference; untyped open objects; container-valued enums; recursive/remote references; unresolved pointers; `allOf`, `not`, conditionals and dependency keywords; tuple arrays; uniqueness; patterns, formats and string-length constraints; `patternProperties`; required undeclared keys; unsupported keywords and resource-limit violations.

Some refused constructs are supported by current model providers. A local refusal is a compiler scope choice, not a claim that the provider rejects that feature. Unused definitions are not a promise of feature support when later referenced.

## Resource and representation limits

JSON values, source schemas and expanded wire schemas are limited to 1,000,000 canonical UTF-8 bytes, 20,000 nodes and depth 64. Bundles must fit the same JSON limits; a separately valid source and wire schema can jointly exceed a bundle's budget. CLI input files also have a 1,000,000-byte read limit, including any BOM or whitespace.

Compilation has a 4,000-node expansion and depth-48 limit. The conservative wire profile allows up to ten container levels, 5,000 properties, 1,000 enum values and the documented name/enum character budgets. Reference expansion and presence wrappers can reach these limits before the source schema does.

Numbers use Python JSON parsing and the installed `jsonschema` validator. Binary floating-point `multipleOf` can reject apparently decimal-exact values, for example `0.3` with `multipleOf: 0.1` under the tested version. No tolerance or decimal coercion is added. Use integer units when exact decimal arithmetic is a requirement, and test your contracts. Textual number spelling and cross-language numeric precision are not preserved.

The [historical benchmark](BENCHMARK.md) exercised 87 external assertions and explicitly excluded 256. It is not a full conformance result. The [live evaluation](REALWORLD_EVALUATION.md) establishes provider acceptance only for its submitted schemas and model snapshot.
