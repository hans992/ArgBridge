# Real-provider tool-calling evaluation

Status: the frozen 995-request live run completed on 29 October 2026. [Results and engineering decision](../../docs/REALWORLD_EVALUATION.md). The offline artifacts remain unchanged as the pre-inference record.

This evaluation preserves the existing codec and historical benchmark. It adds a frozen instruction corpus, strict/nonstrict baselines, an evaluation-only schema factoring variant, a scorer and an explicitly gated OpenAI Responses API runner.

## Reproduce the offline preparation

Use a separate virtual environment to avoid replacing the historical benchmark dependency versions.

    python -m venv .venv-eval
    .venv-eval/Scripts/python -m pip install -r evals/realworld/requirements-lock.txt
    .venv-eval/Scripts/python -m pip install --no-build-isolation --no-deps -e .
    npm --prefix bench/node ci --ignore-scripts --no-audit --no-fund
    .venv-eval/Scripts/python -m evals.realworld.harness prepare --output evals/realworld/runs/prepared-new
    .venv-eval/Scripts/python -m pytest tests/test_realworld.py -q

Use .venv-eval/bin/python on macOS/Linux. Node must be on PATH, or set ARGBRIDGE_NODE_BIN to its executable. tiktoken may download its public tokenizer data the first time; TIKTOKEN_CACHE_DIR can select a local cache. This download is not inference.

The generated plan.json contains all request bodies and is intentionally gitignored because it repeats the frozen corpus almost a thousand times. Preparation requires a fresh output directory and writes its own offline.json and disabled approval template there. No API key is read by prepare. The checked-in artifacts/offline.json belongs to the historical source at commit `a9cd459c8cd58624af8102e1dc714c81678a79f9`; only that exact source and dependency set reproduces its plan hash. The alpha's revised explicit-path manual comparator is separate from this frozen six-arm harness.

## Dataset and oracle

56 synthetic English instructions, eight per primary category: omitted fields, explicit nulls, ordinary updates, nested properties, dictionaries, ambiguity, and invalid/adversarial input. Four workflows cover flat settings, nested settings, arbitrary label keys and a required-fields control.

scenarios.json contains instructions, category and workflow only. expected.json separately records an explicit action and, for updates, the exact expected patch. expected outcomes and rationales are never sent to the model. Dataset hashes are frozen in dataset/MANIFEST.json.

The same analyst authored the dataset and harness. This is a frozen, separately defined oracle, not an independently authored or blind customer holdout. It is small and does not estimate production traffic.

Primary semantic correctness requires the right tool and the exact intended patch, including member presence. A second metric checks the final in-memory state. These are separate because a redundant or unintended mutation can leave today's state unchanged. Clarification/rejection requires the right action and a nonempty reason; nuanced explanation quality is not graded.

## Treatment arms

1. ArgBridge: existing unmodified wire schema and decoder.
2. Factored ArgBridge: repeated schema nodes become local references and repeated generated presence guidance is shared. Wire values and decoder are unchanged.
3. Handwritten strict operations: a typed operation-list wrapper maintained specifically for these four workflows. It was intended as a strong strict control. A post-run inspection found that its nested field mapping was insufficiently documented for the model; see the results before interpreting its ranking.
4. Original non-strict tools: original schemas, explicitly strict: false, followed by original-schema validation.
5. OpenAI Agents strict conversion: current installed strict-schema conversion and original-contract guard.
6. Mastra strict conversion: current installed OpenAI compatibility layer and its exported null normalizer, followed by the same original-contract guard.

See [SDK comparison](../../docs/SDK_COMPARISON.md) for exact scope. The SDK arms measure these named transformations, not every full-framework integration path. No claim of a framework-wide defect follows from a transformation-level result.

Every arm receives the identical natural-language instruction, original contract, initial state, policy, model and settings. Tool representations differ by design. Model responses are never forwarded to a real application: state changes are simulated locally.

## Model and schedule

The frozen configuration uses gpt-5.4-mini-2026-03-17 through Responses, reasoning effort none, temperature 0, max_output_tokens 512, parallel_tool_calls false, service_tier default, and store false.

This is a currently documented, pinned model snapshot; it is not claimed to be OpenAI's newest model. Its snapshot and known tokenizer mapping support reproducible low-cost testing. GPT-4.1 was not selected because its current model page marks it deprecated. GPT-6.1 Terra was not selected for this initial run because the installed tokenizer does not map it; an assumed tokenizer would mislabel token counts.

The plan has 35 schema probes and 960 intent requests: 995 total. Three repetitions share the same 56 scenarios and are interleaved in a deterministic randomized order. OpenAI Agents rejects the dictionary workflow locally, excluding 48 intent requests. Unsupported cells remain explicit and count against coverage.

The schema probes cover 23 supported method/workflow combinations plus all 12 original codec benchmark schemas. A successful HTTP response establishes request acceptance for the submitted configuration, not universal provider compatibility. Non-strict acceptance is labeled separately from strict acceptance through each record's request_strict field.

Three repeats are not three independent datasets. Results should be inspected by scenario and category, with paired gains/losses against the handwritten and non-strict controls. Do not infer production safety from this sample.

## Measurements

- Exact local tokenizer counts for canonical JSON schema content, using tiktoken 0.14.0 and its model mapping to o200k_base.
- Reference argument counts explicitly labeled deterministic, not model output.
- During a live run: tokenizer counts of the actual returned argument strings, raw response usage, cached/uncached input and output tokens, provider latency and total harness latency.
- Structural validity, exact intended-patch correctness, final-state correctness, wrong accepted mutations, refusals, incomplete responses, decode failures and schema rejection.
- Usage-derived inference cost per correct intent operation. Schema-probe costs are separate setup costs. Unknown charges make affected cost-per-correct metrics unavailable.
- Paired encoding gains/losses, including rejected-schema skips, on common attempted scenarios. Unsupported coverage is reported separately.

Canonical JSON content token counts are exact for that representation. They are not a claim about the provider's hidden tool serialization or billed input tokens. Response usage supplies the actual provider token accounting once a live run occurs.

## Spending controls

No paid request occurs in prepare or tests. Unit tests use labeled synthetic responses; one test exercises the real SDK against a mock HTTP transport while network sockets are blocked. Those tests are not provider evidence.

live requires all of:
- An explicitly authorized approval JSON bound to the exact plan hash.
- An approved positive finite USD budget and --allow-spend.
- Matching frozen dataset and implementation hashes.
- A locally configured dedicated OPENAI_API_KEY.
- A fresh run directory.

The CLI consumes an authorization once to prevent accidental duplicate runs. It records a request-start reservation before sending. Automatic SDK retries are disabled. It reserves a conservative per-request amount, settles against response usage, and halts on ambiguous charges, unexpected pricing, authentication/configuration failures or a budget boundary. A process interruption or unknown charge needs review before another authorization is used.

This is a local engineering spending guard, not an OpenAI invoice cap. Token serialization and billing rules remain provider-controlled; use an API project with appropriate external spending controls as well. A ChatGPT subscription does not authorize or include this API run.

The checked-in authorization.example.json is disabled. An actual approval file and raw live runs are gitignored. Do not put API keys in JSON approval files, code, issues or commits.

Example after explicit approval, with a locally created authorization file:

    python -m evals.realworld.harness live --plan evals/realworld/runs/prepared-new/plan.json --authorization evals/realworld/authorization.local.json --allow-spend --max-usd 5 --output evals/realworld/runs/run-001

Do not edit an approved plan or code underneath a run. Regenerate and review it if changes are needed.

## Evidence needed for a readiness decision

A strong result must include real acceptance, zero unintended accepted clears in this dataset, and accuracy competitive with the carefully written strict control at an acceptable measured cost. A schema-size improvement alone is insufficient. If the handcrafted/current alternatives match the workflow with less overhead, report that result directly.

The completed run supports acceptance of the submitted schemas and measured accuracy for this corpus. It does not establish production readiness or superiority over the strongest controls. The decision is to retain ArgBridge as a research artifact.

## Recompute the published live analysis without inference

Use a disposable checkout of historical commit `a9cd459c8cd58624af8102e1dc714c81678a79f9`, its pinned evaluation environment and its original `prepare` command (without --output) to recreate the hashed plan. Then, in that checkout, run:

    python evals/realworld/analysis/report.py . evals/realworld/artifacts/live-2026-10-29 analysis.local.json

This reads published synthetic records and writes aggregate metrics and failure examples. It does not load an API key or make requests. `analysis/audit.py` was used against the locally preserved complete raw run to re-score every intent and recalculate usage costs; the resulting audit is published. Opaque provider response/call IDs are omitted from published records. Output argument strings and usage are retained.

The live plan was executed without changing the frozen dataset, wire schemas, baseline adapters or scorer. Post-run findings, including the handwritten baseline limitation, are documented rather than silently repaired in the original run.
