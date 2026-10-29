# Current SDK comparison

Checked 28–29 October 2026. The implementation review below records local executions and current source observations. The separate [live evaluation](REALWORLD_EVALUATION.md) now measures these exact paths with model-generated arguments.

## OpenAI Agents SDK 0.24.0

The evaluation installs openai-agents 0.24.0 with OpenAI Python 3.41.0, independently of the historical benchmark environment.

The current [strict-schema converter](https://github.com/openai/openai-agents-python/blob/main/src/agents/strict_schema.py) includes substantial 2026 work:
- [Bounded reference expansion, July](https://github.com/openai/openai-agents-python/commit/8ce548ef4e758e0ac2902103155af2b77b4273e4).
- [Empty additionalProperties mapping rejection, July](https://github.com/openai/openai-agents-python/commit/9684cef97b2d51691db0e33032fa19ff6ac263c9).
- [Typeless object normalization, August](https://github.com/openai/openai-agents-python/commit/7de6ccf05ddcddcd67839814fea9e4959f22b515).
- [Unsafe reference-sibling rejection, August](https://github.com/openai/openai-agents-python/commit/27c1060185b2fcb1cad756adab201cd2d4e9769c).

These fixes are treated as incumbent capabilities. The benchmark does not use the earlier defects as differentiation.

In the current local fixture, optional nullable fields still become required. The typed-dictionary workflow raises UserError; it does not silently discard dictionary values. Its message recommends non-strict mode when open objects are needed. The evaluation therefore includes an explicit original-schema non-strict arm.

The remaining observed difference is automatic reversible transport for these contracts. The SDK's refusal is sensible behavior; it is not evidence that an application using the SDK cannot solve the task.

## Mastra schema-compat 1.3.17

The package version matches the current [package source](https://github.com/mastra-ai/mastra/blob/main/packages/schema-compat/package.json). The [October optional-union issue](https://github.com/mastra-ai/mastra/issues/26703) is fixed; its historical behavior is not used.

The evaluation executes OpenAISchemaCompatLayer.processToJSONSchema with the selected model profile and StandardSchemaWithJSON input, plus the exported wrapSchemaWithNullTransform normalizer. It validates the resulting patch against the original schema.

Current local observations:
- The required-fields control remains intact.
- Optional nullable fields are represented as required nullable fields.
- In the tested normalizer path, optional explicit null becomes undefined and disappears on JSON serialization.
- The typed dictionary schema is closed, excluding undeclared keys.

This describes the tested exports and configuration. It does not establish how every Zod integration, downstream validator or application-specific wrapper behaves. Raw emitted schemas and the installed version are recorded by the evaluation.

## Strong controls

The handwritten strict operation-list wrapper preserves the frozen scenarios' intended patches in deterministic reference tests and uses fewer schema tokens. Original non-strict tools also retain the JSON contract. Either could be preferable in practice.

ArgBridge's automatic compilation may reduce per-contract wrapper work, but that engineering convenience is not a measured model advantage. The completed paired live evaluation found no accuracy or cost advantage over original non-strict tools with validation. Its handwritten strict control has a documented nested-mapping limitation, so the run cannot rank ArgBridge against a fully specified strict wrapper.

## Sources for the live configuration

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling): strict requirements and explicit non-strict mode.
- [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini): pinned snapshot, supported features and prices.
- [OpenAI tiktoken model mapping](https://github.com/openai/tiktoken/blob/main/tiktoken/model.py): local tokenizer selection. Hidden provider serialization is measured separately through response usage.
