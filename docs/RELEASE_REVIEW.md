# 0.1.0a1 engineering review

Prepared 29 October 2026 from research snapshot `a9cd459c8cd58624af8102e1dc714c81678a79f9`. This is a fresh source review with executable regression checks, not an external security audit or an independently authored model evaluation. The candidate is suitable for experimental engineering review; production suitability is not established.

## Scope and disposition

The review covered the complete runtime, public exports, CLI, schema subset, transformation/validation boundaries, evaluation harness, tests, dependency metadata, packaging and examples. It also reproduced the historical offline benchmark from a disposable checkout. The useful scope remains a bounded, reusable transport codec for strict tools whose original contracts need member presence or typed maps. It is not a general converter, agent framework or model-accuracy improvement.

## Defects repaired

1. **Expanded schemas could exceed the codec's own budget.** Twelve local references to a long description produced a wire schema exceeding one million bytes from a source below the limit. Compilation now checks the generated wire before exposing it and raises `UnsupportedSchema` with `wire_limit`.
2. **A returned bundle could be unreadable by the same implementation.** Even individually acceptable source and wire schemas can exceed the combined budget. `bundle()` now rejects an oversized aggregate before returning it. Regression tests cover both resource cases.
3. **CLI reads were unbounded before parsing.** Input is now read through a byte limit before UTF-8 decoding. UTF-8 BOM input and non-ASCII values are covered; stdout uses portable JSON escapes and files use UTF-8/LF.
4. **Direct dependency and diagnostics were incomplete.** The imported referencing package is now declared explicitly. Unsupported keyword paths escape `/` and `~` as JSON Pointer tokens.
5. **Reproduction commands risked replacing historical evidence.** New benchmark defaults use separate output directories and refuse the historical result root. Evaluation preparation requires a fresh directory, and live mode requires an explicit plan path. Existing evidence and the old live baseline are retained.

The normal wire representation is unchanged. Runtime formatting, method annotations, a single version source and a module entry point improve maintainability without introducing another transport protocol.

## Verification recorded

On Windows 11 / CPython 3.12.14, the full suite passed **110 tests** in 21.458 seconds. This includes the original fixed/property tests, new resource/CLI regressions, the revised handwritten comparator and the real OpenAI SDK through an in-memory mock transport. The minimum-dependency core suite passed **81 tests** in 14.487 seconds with jsonschema 4.23.0 and referencing 0.35.1. Test totals overlap; do not add them together. See [test summary](../bench/results/release-0.1.0a1/tests.json).

All **35 historical data/evidence files** in the preservation manifest retain their SHA-256 hashes. The frozen natural-language corpus and oracle are among them. [Preservation manifest](../bench/results/release-0.1.0a1/preservation.json).

The historical checkout reproduced 40 exact valid round trips, 36 invalid rejections, 12 hostile rejections, 87 exercised external assertions and 256 excluded assertions. The candidate produced the same counts and source/wire byte totals. Twelve intentionally unsupported fixture schemas still receive explicit refusals. The new manual wrapper separately restored all 41 expected update patches; these are deterministic reference inputs, not model outputs.

Historical reproduction median encode/decode time was 0.1991 ms and p95 0.4917 ms, close to the published 0.2024/0.4885 ms. The candidate measured **0.2462 ms median, 0.5608 ms p95 and 34.4377 ms maximum**, across 1,200 operations; compilation median was 1.6184 ms. The candidate run was sequential after setup activity. A preliminary run during file copying measured 0.2454/0.5940 ms with a 41.374 ms maximum. The slower median is consistent with extra checks, but this is not an isolated causal performance study. Large Windows scheduling/runtime tails remain unexplained; neither run is a latency guarantee or competitor timing comparison. [Candidate record](../bench/results/release-0.1.0a1/benchmark.json), [historical reproduction](../bench/results/release-0.1.0a1/historical-reproduction-benchmark.json).

The original twelve schemas still expand **1,611 → 8,305 bytes (5.16x)**. The revised manual wrapper has fewer canonical schema and reference-argument tokens on the four evaluation workflows; see [SDK comparison](SDK_COMPARISON.md). It may be preferable for a small, stable tool set.

## Trust and API assessment

Compilation is explicit and reusable. Schemas are defensively copied; bundle loading recompiles rather than trusting a serialized plan. Source validation, strict-wire validation, duplicate/collision rejection and final source validation are separate boundaries. Duplicate raw JSON keys are rejected by the supplied parser. Remote reference retrieval is disabled and local recursion/expansion is bounded.

The code does not establish authorization, transaction safety or correct model intent. A structurally valid wrong clear can pass validation. `guarded_call` does not make a mutating handler safe or reversible. Schemas must come from trusted application configuration; Python and dependency validators remain in the trusted runtime. Resource bounds are safeguards, not a complete denial-of-service proof.

The schema subset is deliberately narrow. Decimal `multipleOf` inherits Python/jsonschema numeric behavior: for example, the current validator rejects 0.3 as a multiple of 0.1. The codec does not claim decimal financial arithmetic or cross-language numeric equivalence. Unsupported patterns, formats, recursion and other constructs remain documented refusals.

## Integration and release limits

The new OpenAI example defaults to an offline request preview. Its paid path requires two explicit flags, user-supplied credentials and uses zero automatic retries. It returns a decoded proposal without applying it. The SDK transport mock verifies request/response plumbing only. **No new paid inference was executed for this release.** Historical acceptance and model scores are tied to the old frozen experiment, not this new example.

Windows/Linux CPython 3.11–3.15 CI is configured with read-only permissions and pinned action revisions; workflow and issue-form YAML parse checks passed. Hosted CI has not run for this candidate. macOS, alternate interpreters and every allowed dependency combination remain unverified.

The wheel was built from the source distribution, passed strict Twine metadata checks and installed into a fresh environment with only its declared runtime dependencies. Isolated import, CLI version and all three quickstart operations passed. The extracted source distribution also passed 81 core tests. `scripts/check_release.py` checks package contents, retained license files and common credential/local-path patterns. These checks do not upload anything; publication remains a separate owner decision.

The MIT license is retained for owner approval. Runtime dependencies are not vendored; external test-data notices remain attached. Package-name and license metadata checks are documented in [DEPENDENCIES.md](DEPENDENCIES.md). Secret-pattern scans and explicit archive exclusions reduce accidental disclosure but cannot prove the absence of all sensitive information. No credentials, internal brainstorming or owner promotion drafts are intended for the public package.

## Follow-up criteria

The next useful evidence is hosted compatibility results, independently supplied synthetic workflows and a separately approved comparison against the revised manual control. Further encoding changes need round-trip regressions and measured schema/token effects before any new model evaluation. There is no evidence-based reason to add a dashboard or broaden unsupported schema semantics casually.
