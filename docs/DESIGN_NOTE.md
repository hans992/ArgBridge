# When an omitted argument is different from null

A contact-update API can give three meanings to one member: `{}` leaves the name unchanged, `{"name": null}` clears it, and `{"name": "Grace"}` replaces it. A schema adapter that fills missing members with null can turn a harmless omission into a clear operation.

OpenAI strict function calling requires every declared object property to be required and objects to be closed. Optional values can be represented using null, but a nullable source property already uses that value. A transport representation must preserve the distinction somewhere else. See the [provider's function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling).

## The encoding

ArgBridge represents an optional field using one of two closed objects:

```json
{"state": "absent"}
```

```json
{"state": "present", "value": null}
```

The value can also be a valid non-null value. Typed maps travel as lists of key/value entries, so the wire schema can remain closed while the original keys remain dynamic. Duplicate entries and attempts to shadow fixed fields are rejected.

The compiler builds a transformation plan once. Encoding validates the source value; decoding validates the wire, reconstructs the source representation, then validates that against the original contract. That final check matters: a tagged union branch alone does not enforce the exclusivity of an original `oneOf`, for example.

The goal is equality of JSON values and member presence. It is not preservation of whitespace, key order or floating-point text. Remote references, recursion and unsupported schema constructs are refused rather than approximated.

## Correct transport is only one layer

The deterministic benchmark restores 40 valid inputs and rejects 36 invalid inputs and 12 hostile cases. Of 343 externally authored assertions, 87 exercise the supported subset and 256 are explicitly excluded. Those exclusions are a substantial limit, not incidental noise.

The encoding also costs space: the original twelve-schema corpus expands from 1,611 to 8,305 bytes, or 5.16 times. A schema-factoring experiment reduces that to 4.67 times without changing wire values. Neither byte count is a substitute for actual model token accounting.

The real-model result is less favorable. Across the historical 995-request experiment, ArgBridge achieved 91.1% exact intent accuracy; the original non-strict tools with local validation achieved 96.4%. ArgBridge cost about 46% more per correct intent in that run. Valid tool arguments sometimes still represented the wrong action. See the [complete evidence and limitations](REALWORLD_EVALUATION.md), including the flawed description in the original handwritten control.

That result defines a narrower use case: reusable reversible transport when strict schemas are an integration requirement. It does not justify choosing ArgBridge to improve model reasoning. For a few fixed tools, a carefully written operation list may be clearer and smaller. If non-strict tools are acceptable, they are a strong starting point.

## What the alpha adds

The release candidate keeps that narrow scope. It adds a small installable package, bounded CLI input, checks on expanded schema and bundle size, explicit API documentation, reproducible tests and an offline-first OpenAI request example. The example's real SDK request and decoding path are tested through a mock transport; the exact new request has not been submitted to the provider.

The remaining work is measurable: independent workflow cases, broader compatibility results, and a newly approved paired model evaluation of the revised explicit-path wrapper. Claims should grow only as that evidence grows.
