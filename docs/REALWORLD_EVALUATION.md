# Real-world evaluation: offline findings

As of 29 October 2026, the harness is prepared and tested; no live-provider request has been made. Schema acceptance, model accuracy, generated argument tokens, provider latency and inference cost per correct operation are explicitly null in the recorded offline artifact.

## Frozen comparison

56 instructions, four workflows, six treatment arms, three repetitions. The prepared schedule contains 995 requests: 35 schema probes and 960 intent trials. The Agents strict-conversion arm locally rejects the dictionary workflow, so 48 of the otherwise planned 1,008 trials are unsupported; this is recorded rather than hidden.

The model is gpt-5.4-mini-2026-03-17 with identical settings across arms. Expected outcomes are held in a separate file and are not sent to the provider. See the [evaluation protocol](../evals/realworld/README.md).

## Actual local token counts

Using the documented model identifier with tiktoken 0.14.0, canonical schema content is tokenized with o200k_base.

On the original twelve-schema corpus:
- Original source schemas: 415 tokens.
- ArgBridge wire schemas: 1,874 tokens.
- Factored wire schemas: 1,750 tokens, a 6.6% reduction.
- Wire bytes: 8,305 to 7,527; compared with 1,611 source bytes, the byte expansion falls from 5.16× to 4.67×.

On the new workflows:
- Flat update: 358 original wire tokens, 296 factored, 173 handwritten strict.
- Nested update: 534 original, 375 factored, 213 handwritten strict.
- Typed labels: 326 original, 326 factored, 166 handwritten strict.
- Required-fields control: 63 original, 63 factored, 44 handwritten strict.

Factoring helps repeated optional structure, but does not remove the overall overhead. The handwritten baseline is smaller on all four workflows. Original non-strict schema counts are 73, 72, 56 and 44 respectively.

These are exact tokenizer counts for canonical JSON content, not billed API prompt tokens. No generated-argument measurements exist yet. Deterministic reference arguments are recorded separately and labeled accordingly.

## Correctness of the smaller schema

The original codec implementation and wire messages are unchanged. The experiment shares repeated presence guidance and factors identical schema nodes into local references. Expanding those references yields identical non-annotation schemas; the original valid corpus and generated presence cases pass against both forms.

This proves a local representation equivalence, not provider acceptance or model comprehension. Additional references could help or harm model behavior.

## Cost estimate and readiness

The prepared run estimates US$3.10 at the verified standard rates: US$0.75/M input and US$4.50/M output tokens, with no cache discount. The estimate gives every request the full 512-output-token allowance and adds input headroom to local content counts. It is an estimate, not a provider quote.

The runner has single-use approval, plan/data/code hashes, no automatic retries, request reservations and stop conditions for unknown charges. Paid execution is disabled until explicitly authorized.

Current status: retain as an experimental library pending actual provider evidence. The offline data supports a correct codec and modest schema compression; it does not justify a claim of superior model reliability or production suitability. The current handwritten and non-strict alternatives remain credible controls.
