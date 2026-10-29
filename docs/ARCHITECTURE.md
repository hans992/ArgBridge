# Architecture and scope

## Boundary

Source schema → compile once → wire schema + internal transformation plan.

Existing valid JSON → encode → wire JSON → decode → original JSON validation → optional caller-supplied handler.

For model integration, the model generates wire JSON directly from its instruction and the emitted schema. The separate [live evaluation](REALWORLD_EVALUATION.md) exercises this step and observes validly shaped but unintended updates. Schema validation cannot detect those intent errors.

## Representation

Every wire message has an arguments member inside a closed root object.

- Required properties retain their values through the child codec.
- Optional properties become either {state: "absent"} or {state: "present", value: ...}. A nullable child therefore retains three distinct states.
- Typed dictionaries become {entries: [{key, value}, ...]}. Mixed fixed/dynamic objects use {fields, entries}. Entries cannot duplicate each other or shadow any declared field.
- Arrays map their elements through the child codec.
- anyOf/oneOf and unions containing containers use variant tags. Encoding picks the first valid branch; decoding checks the tag, validates its wire branch, then validates the entire original schema.
- Scalar values are copied without stringification or coercion.
- Local acyclic references are expanded. Recursive, remote and ambiguous reference forms are refused.

A JSON Schema oneOf can reject a value that individually matches a tagged branch because it also matches another branch. That exclusivity check is retained at the original-schema validation boundary. The local wire schema alone is therefore not the complete acceptance policy.

Descriptions and titles are retained, including reference and union descriptions. Defaults are annotations: the codec never inserts default values for omitted members.

## Supported source subset

Draft 2020-12 only. Explicit primitive types and primitive unions; scalar enum/const; typed arrays with minItems/maxItems; closed objects; objects with a schema for additionalProperties; declared required fields; anyOf/oneOf without assertion siblings; local acyclic JSON Pointer references; numeric bounds/multipleOf.

Annotations such as default and examples do not change runtime validation. Inapplicable type-specific keywords retain ordinary JSON Schema semantics: for example, minimum does not constrain null.

Conservative refusals include implicit/unconstrained types, boolean schemas, untyped open objects, container-valued enums, combined enum+const, recursion, external references, assertion siblings of references or unions, patterns/formats/string-length constraints, patternProperties, dependencies, conditionals, allOf/not, tuple arrays, uniqueness, and unrecognized keywords. These are scope limits, not claims that providers cannot ever support those constructs.

## Implementation

- src/argbridge/core.py: compilation, resource limits, JSON parsing, wire checks, original contract guard and bundle verification.
- src/argbridge/cli.py: compile/encode/decode file interface.
- examples/demo.py: in-memory update semantics and rejection demonstration.
- bench/run.py: independent reference validation, baselines, installed SDK helper, exclusions, timings and sizes.
- bench/node/compare.mjs: pinned current Mastra conversion and normalizer observations.
- tests/test_contracts.py: frozen fixtures, independent suite assertions, generated contracts, mutation tests and CLI behavior.

Runtime source and wire schemas are defensively copied. Bundles are recomputed, not executed as supplied transformation plans. External reference retrieval is disabled.

## Resource and trust limits

JSON is bounded to 1 MB, 20,000 nodes and depth 64; compilation has a 4,000-node expansion budget and depth bound. Emitted wire schemas are checked against a conservative local profile with ten container levels, 5,000 properties, 1,000 enum values and documented character budgets.

The local profile implements a subset of the provider documentation, not the provider's parser. It may conservatively refuse shapes a provider accepts. The live evaluation established acceptance of the twelve original benchmark wire schemas and four workflow schemas for one OpenAI model snapshot; acceptance of other emitted schemas remains unverified.

Errors expose constraint names and paths, not complete input values. Paths may themselves contain caller data. The module is not an isolation boundary against malicious Python objects, arbitrary handler code or every possible denial of service. It accepts ordinary bounded JSON and trusted application schemas.

Round-trip equality concerns JSON data and member presence, not whitespace, key order, floating-point text spelling or precision beyond Python's parsed representation. No JavaScript port or cross-language numeric guarantee is claimed.
