# Offline benchmark â€” 28 October 2026

## Result

The offline benchmark passed on the selected subset. The full machine-readable record is [benchmark.json](../bench/results/benchmark.json); comparator outputs, tests and demo are alongside it.

- 40 valid workflow inputs: all exactly restored, including omitted versus null members.
- 36 invalid source inputs: all rejected before encoding.
- 12 hostile wire/JSON cases: all rejected, zero handler calls.
- 12 deliberately unsupported schemas: all returned explicit refusal.
- 87 externally authored instance assertions: zero disagreements.
- 256 external assertions excluded because their schemas were outside the subset.
- External group coverage: 19 of 105 groups, across all ten preselected files. Exclusions remain individually listed with locations/reasons.

The external dataset supplies genuine author independence. The local workflow fixture and implementation share an author, and were not a blind holdout. The selected corpus was frozen before application code existed; input hashes are included in the benchmark record. Additional review tests are labeled as such.

The final pytest run passed 56 tests in 9.18 seconds, including five generated/property tests with 500 passing examples each. Hypothesis also discarded 214 generated draws while satisfying generation constraints; those are generator rejections, not application failures. The external suite assertions and frozen workflows are exercised inside the test functions, so these counts must not be added together as independent tests.

## Baselines

The deterministic baselines are implemented in bench/run.py. They receive the same original schema and valid input values.

For the five update cases, requiring all fields and closing objects restores 1/5; four original messages are rejected. A nullable fill plus schema-aware removal of newly introduced nulls also restores 1/5; four messages lose member-presence semantics. ArgBridge restores 5/5.

For the three typed-dictionary cases, both closing baselines restore only the empty dictionary, 1/3. ArgBridge restores 3/3.

On the ordinary required-fields workflow and required-nullable workflow, both baselines and ArgBridge restore every case, 2/2 in each. Optional non-null scalar recovery also works in the stronger nullable baseline. The distinction is not that all nullable adapters are broken.

These figures describe the selected fixtures, not an estimated distribution of production traffic.

## Current installed alternatives

OpenAI Python 3.40.0: the actual private _ensure_strict_json_schema helper was executed. It makes the tested optional nullable name required. It preserves the typed additionalProperties schema, so nonempty maps validate locally, but that output remains open and does not satisfy the closed-object contract under test. This helper is not advertised here as a general codec; the experiment does not benchmark its entire public SDK.

Mastra schema-compat 1.3.17 with the OpenAI gpt-4.1 compatibility profile: the actual exported processToJSONSchema method was executed with a StandardSchemaWithJSON input, following the API shape in the recent fixed issue. The optional nullable name becomes required, and the typed map becomes additionalProperties: false with no declared map keys. The two nonempty dictionary inputs fail against that emitted schema.

The exported wrapSchemaWithNullTransform function was also probed in isolation: an optional explicit-null name becomes undefined (and disappears on JSON serialization); a required nullable field retains null. The inner validator was deliberately pass-through to observe only normalization. This is not a complete agent execution benchmark.

Mastra's profile also moves some numeric/array constraints into descriptions. The benchmark reports any source-invalid instances allowed by its emitted schema, but does not claim those reach a real Mastra handler: downstream validation can reject them.

[OpenAI output](../bench/results/openai-sdk.json), [Mastra output and probes](../bench/results/mastra.json), package locks and file hashes make these observations reproducible. No historical SDK defect was substituted for the current version.

MCP Inspector already provides portability linting. TanStack has schema-aware null-widening recovery. They were examined as documented alternatives, not timed or executed here. A handwritten tagged wrapper or an entry-list API can also preserve these semantics; this experiment demonstrates an automatic compiler/guard for its subset. Tagged encodings themselves are established techniques.

## Latency and cost

On the recorded Windows host with Python 3.12, after compilation:

- 1,200 encode+decode operations, including source and wire validation.
- Median 0.2024 ms; p95 0.4885 ms; maximum 0.9200 ms.
- Compilation across 12 schemas: median 1.4142 ms; maximum 2.3947 ms.
- Acceptance thresholds: median under 20 ms and p95 under 50 ms.

Warm-up, repetitions and percentile calculation are in bench/run.py. These are local wall-clock measurements, not model latency, competitor latency or throughput under concurrency. Reproduction will vary with the host.

No model, hosting or paid-service call was made by the prototype. Its incurred inference charge is zero because it performs no inference; the surrounding research session's cost is not included. At the measured median, 10,000 serial codec pairs would take about 2.0 seconds of this local execution time (linear extrapolation, not a capacity test). A monetary CPU estimate would require an actual deployment price and utilization.

## Significant cost of the representation

Aggregate source schema size is 1,611 UTF-8 bytes; emitted wire schema size is 8,305 bytes: 5.16Ã—. For the update workflow alone, schema size rises from 213 to 1,510 bytes. One sparse 10-byte input becomes a 106-byte wire message; the fullest tested 51-byte update becomes 149 bytes.

Schema descriptions explain the new protocol and contribute to expansion. Byte counts are not token counts. Inference price, prompt caching, semantic generation error rate and end-to-end latency were not measured in this historical offline benchmark; see the separate [live evaluation](REALWORLD_EVALUATION.md). A technically lossless codec may still be a worse model interface.

## Interpretation

The bounded transport/guard hypothesis is supported. Universal schema support, live strict-mode compatibility, model intent accuracy, customer savings and willingness to pay are not established. Live model accuracy and provider acceptance require a separate evaluation.
