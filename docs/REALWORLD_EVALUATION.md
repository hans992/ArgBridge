# Live provider evaluation — 29 October 2026

Historical evaluation of the frozen research implementation. The alpha release improves packaging and developer experience without changing these measurements or claiming live results for its new example.

**Engineering decision: retain ArgBridge as a research project.** The codec is correct on its deterministic tests, and the real provider accepted the submitted schemas. This run did not demonstrate a model-reliability, latency or cost advantage over original non-strict tools with local validation. Further product features are not justified by these results.

The strongest observed control achieved 162/168 correct intents (96.4%), versus 153/168 (91.1%) for ArgBridge and 155/168 (92.3%) for its factored schema. ArgBridge cost 46.1% more per correctly completed intent and had higher median latency. All three still made intent errors; none is established as production-safe by this sample.

## What was actually run

995 real OpenAI Responses requests: 35 schema probes and 960 intent trials. The frozen corpus has 56 synthetic instructions across four workflows, with three repetitions and six arms. The same original contract, initial state, policy, natural-language instruction and model settings were used across arms. Only the tool representation differed. No real application handler was invoked.

Model: `gpt-5.4-mini-2026-03-17`; reasoning `none`, temperature 0, maximum output 512 tokens, parallel tool calls disabled, `store: false`, default service tier. The schedule, expected outcomes and schemas were frozen before inference at commit `d336b24cda619d4798919355853304c25da65c3a`. The expected outcomes were never sent to the model.

All 995 requests completed without an API error, retry, unknown charge or budget stop. Provider usage reported 507,171 input tokens, zero cached input tokens and 37,677 output tokens. At the documented rates, total usage-derived cost was **US$0.54992475**, including US$0.01743750 for schema probes. This is calculated from provider token usage, not an independently reconciled invoice. The earlier US$3.10 estimate reserved the full output allowance for every request.

## Provider acceptance and structural validity

All 35 schema probes were accepted: 31 strict requests and four explicit non-strict requests. These cover all 12 original ArgBridge benchmark wire schemas and the 23 supported method/workflow combinations, including four factored ArgBridge schemas. Strict tool settings were echoed by the provider. Acceptance is established for these submitted schemas, snapshot and API configuration; it is not a claim about every schema supported by the compiler or every provider/model.

All 960 intent responses contained exactly one tool call, parsed as valid JSON, conformed to their tool schema and passed the applicable local validation path. The original-contract guard accepted every returned update. **Structural validity was 100%; semantic correctness was not.** Non-strict responses also happened to validate in this finite sample; non-strict mode provides no constrained-generation guarantee.

## Intent accuracy and cost

Exact correctness requires the correct action and patch, including member presence. A redundant write can fail this metric while leaving the current final state unchanged. Clarification/rejection is scored by action and nonempty reason, not by a qualitative assessment of the explanation.

| Arm | Exact correct / observed | Accuracy | Wrong accepted nonempty patches | USD / correct intent |
| --- | ---: | ---: | ---: | ---: |
| ArgBridge | 153/168 | 91.1% | 10 | $0.000724 |
| Factored ArgBridge | 155/168 | 92.3% | 8 | $0.000690 |
| Handwritten strict* | 138/168 | 82.1% | 3 | $0.000660 |
| Original non-strict + validation | 162/168 | 96.4% | 3 | $0.000495 |
| Agents strict conversion** | 39/120 | 32.5% | 75 | $0.001574 |
| Mastra strict conversion** | 93/168 | 55.4% | 54 | $0.000884 |

Costs in this table cover all attempted intent requests in the arm, divided by exact correct intents; they exclude the separate schema probes. They include clarification and rejection operations. The denominator is not limited to successful updates.

*The handwritten control has a material post-run limitation: its nested wrapper uses leaf names such as `timezone` without explicitly stating the mapping to `settings.timezone`. Actual responses cite this mismatch when asking for clarification. It scored 29/48 on the nested workflow, versus 42/48 for ArgBridge and 48/48 for original non-strict. Its aggregate result cannot establish superiority over a fully documented, tuned strict operation wrapper. The frozen baseline was not changed or rerun after seeing the failures.*

**These are the exact current SDK transformation paths described in the [SDK comparison](SDK_COMPARISON.md), not end-to-end framework rankings. Agents rejected the dictionary schema locally, so it ran 120 rather than 168 intents. The 48 unsupported trials remain explicit; counting them against full coverage gives 39/168 = 23.2%. Mastra ran all 168. Current SDKs can host manually designed wrappers or non-strict tools; these results do not show that the frameworks cannot implement the workflow.**

ArgBridge returned ten wrong nonempty patches: seven produced the wrong final state and three redundantly wrote the already-current theme. Factored ArgBridge returned eight: five wrong final states and three redundant theme writes. Original non-strict returned three wrong nonempty patches, all clearing a quota when the oracle required clarification. The raw scorer's `unsafe_accepted_mutation` flag means a wrong nonempty patch; it is not evidence of real-world harm or even a changed final state in every case.

## Paired losses and concrete failures

On the 168 paired trials, original ArgBridge lost nine cases that original non-strict got right and gained zero. Factored ArgBridge lost seven and gained zero. These are observed paired discrepancies, not proof of causation or statistical generalization to customer traffic. Three repetitions share each scenario.

- `null-04`: "Clear the saved timezone so that the field is absent." Expected `{"settings":{"timezone":null}}`. Original ArgBridge instead encoded the timezone as absent and decoded to `{"settings":{}}` on all three repetitions, preserving the timezone. Both ArgBridge variants failed all three; original non-strict passed all three. A reversible codec did not prevent the model from confusing omission with a requested clear.
- `nested-08`: "Explicitly retain the dark theme and change timezone to UTC only." Both ArgBridge variants wrote the existing theme as well as the timezone on all three repetitions. Final state was correct, exact patch intent was not. Original non-strict omitted the theme correctly.
- `ambiguous-06`: original ArgBridge inferred a ticket and target priority on one repetition of "Increase the ticket priority", where the frozen policy required clarification. This is a model decision error, not a decoding error.
- Shared errors remain: original non-strict, ArgBridge and factored ArgBridge all asked unnecessary clarification for the explicitly requested string `"null"`, and all cleared quota for "Set the quota to nothing" instead of clarifying. Original non-strict is a stronger observed control, not a fully reliable solution.

The original and factored codecs introduced no observed JSON, wire-validation or decoding failures. Their extra failures were validly encoded wrong intentions. The two-response aggregate gain from factoring does not establish a reliable accuracy improvement.

## Category breakdown

The category describes the instruction's primary stressor; workflow is recorded separately. Each full-coverage cell has 24 trials. A `0/0` cell denotes unsupported coverage, not a zero-percent measured result.

| Category | ArgBridge | Factored | Handwritten* | Non-strict | Agents** | Mastra** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| omission | 24/24 | 24/24 | 22/24 | 24/24 | 0/21 | 17/24 |
| null | 21/24 | 21/24 | 21/24 | 24/24 | 0/15 | 0/24 |
| ordinary | 21/24 | 21/24 | 18/24 | 21/24 | 9/24 | 22/24 |
| nested | 21/24 | 21/24 | 13/24 | 24/24 | 0/24 | 12/24 |
| dictionary | 24/24 | 24/24 | 19/24 | 24/24 | 0/0 | 0/24 |
| ambiguous | 20/24 | 20/24 | 21/24 | 21/24 | 15/18 | 21/24 |
| invalid | 22/24 | 24/24 | 24/24 | 24/24 | 15/18 | 21/24 |

## Token and latency overhead

Argument counts below tokenize the actual returned argument strings with `tiktoken 0.14.0` and `o200k_base`; they include reasons as well as updates. Provider usage includes tool-call formatting and other tokens, so it need not equal argument-string counts. Input and output totals are for intent requests, with no cache hits.

| Arm | Mean argument tokens | Provider input / output tokens | Provider latency p50 / p95, seconds | Harness latency p50 / p95, seconds |
| --- | ---: | ---: | ---: | ---: |
| ArgBridge | 34.7 | 99,273 / 8,065 | 1.030 / 1.444 | 1.030 / 1.447 |
| Factored ArgBridge | 34.9 | 93,930 / 8,095 | 0.987 / 1.413 | 0.987 / 1.416 |
| Handwritten strict* | 24.1 | 83,406 / 6,325 | 0.952 / 1.464 | 0.952 / 1.465 |
| Original non-strict + validation | 14.9 | 78,612 / 4,736 | 0.850 / 1.273 | 0.851 / 1.274 |
| Agents strict conversion** | 21.5 | 56,709 / 4,191 | 0.880 / 1.219 | 0.880 / 1.220 |
| Mastra strict conversion** | 17.4 | 78,609 / 5,162 | 0.882 / 1.257 | 1.037 / 1.503 |

Provider latency measures SDK request start through response receipt, including network and provider processing. Harness latency additionally includes local scoring/decoding; it excludes a real downstream application because no handler was called. Mastra's measured harness latency includes launching its Node adapter for decoding; this is not a claim about a persistent Mastra application's latency. Requests were sequential in a randomized frozen schedule; latency comparisons describe this run and environment.

Canonical schema-content counts are separate from provider-billed input tokens:

| Workflow | ArgBridge | Factored | Handwritten | Original non-strict |
| --- | ---: | ---: | ---: | ---: |
| Flat update | 358 | 296 | 173 | 73 |
| Nested update | 534 | 375 | 213 | 72 |
| Typed labels | 326 | 326 | 166 | 56 |
| Required-fields control | 63 | 63 | 44 | 44 |

On the original twelve-schema corpus, source schemas occupy 415 tokens, original wire schemas 1,874, and factored schemas 1,750: a 6.6% reduction. Bytes decrease from 8,305 to 7,527 against 1,611 source bytes, reducing expansion from 5.16x to 4.67x. The original raw benchmark remains unchanged.

Factoring shares repeated generated presence guidance and identical schema nodes through local references. Expanded non-annotation schemas remain equivalent in local checks, and wire values and the original decoder are unchanged. The four factored workflow schemas were accepted live. This run reduced intent-request cost by 3.5% compared with original ArgBridge, while mean argument tokens stayed essentially unchanged. Compression did not eliminate the overhead or the semantic failures.

## Competitive interpretation and next step

ArgBridge still demonstrates automatic reversible transport that the tested strict SDK transformations do not supply for optional-nullable fields and typed dictionaries. That is a narrow engineering capability. It did not produce better model outcomes than the original non-strict contract plus validation in this run, and wrapper-development time was not measured.

The code, deterministic evidence and live evaluation remain available as an MIT-licensed research artifact. Further development would require a concrete integration that needs strict generation and a new held-out evaluation against an explicitly documented manual wrapper showing a useful advantage. These results do not establish production suitability.

## Evidence and limits

- [Published synthetic provider records](../evals/realworld/artifacts/live-2026-10-29/records.json): arguments, response status, usage, latency, scores, request hashes and returned strictness; opaque provider IDs omitted.
- [Analysis](../evals/realworld/artifacts/live-2026-10-29/analysis.json), [runner summary](../evals/realworld/artifacts/live-2026-10-29/summary.json), and [offline audit](../evals/realworld/artifacts/live-2026-10-29/audit.json).
- All 960 scores and 995 usage-cost calculations were recomputed from the saved raw responses with zero discrepancies. This verifies consistency using the same scorer; it is not an independent audit of the oracle. The scorer, compiler, dependencies and dataset hashes matched the frozen plan.
- Plan SHA-256: `9dd0cb4526f5d63f792b51147770e348cbc92ec66b312683fd49d58e06b00df0`. See the [frozen protocol and reproduction steps](../evals/realworld/README.md).
- One model snapshot, one run, four small synthetic workflows, 56 English instructions and three correlated repetitions. The same analyst authored the corpus and scorer. No customer data, blinded holdout, load test, multi-model test, retry loop, real handler or measured demand is represented.
- This is real model-generated evidence. Original round-trip/property tests, reference arguments and compression equivalence checks remain separately labeled deterministic evidence.

Configuration and pricing sources: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [GPT-5.4 Mini model and rates](https://developers.openai.com/api/docs/models/gpt-5.4-mini), and [current SDK review](SDK_COMPARISON.md).
