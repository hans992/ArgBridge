# Compatibility

The release candidate requires CPython 3.11 or newer. Python 3.11–3.15 are configured in the Windows/Linux CI matrix. Local release checks were run on CPython 3.12.14 and Windows; the remaining matrix is pending CI execution after publication approval. CI configuration alone is not a passing result. macOS and alternative interpreters are not locally verified.

The runtime declares `jsonschema>=4.23,<5` and `referencing>=0.35.1,<1`. The current local environment uses 4.26.0 and 0.37.0. Core installation needs no Node, OpenAI SDK, model, tokenizer or credentials.

The optional OpenAI example uses `openai>=3.41,<4`. Its offline request/response adapter is tested separately from the historical real-provider experiment. The historical run used OpenAI Python 3.41.0, Agents SDK 0.24.0, Mastra schema-compat 1.3.17, tiktoken 0.14.0 and a pinned model snapshot. It does not establish live acceptance of every new example, current release schema or future SDK/model.

The benchmark comparator requires Node 24 and its pinned npm lock. Pinned benchmark environments are separate from the minimal package installation. The evaluation dependency lock includes platform markers for Windows-only packages.

The distribution is `argbridge`; the import and CLI are also `argbridge`. The old research distribution was named `argbridge-experiment`. Both expose the same import path, so uninstall the old distribution before installing the new wheel into the same environment, or use a fresh environment. `0.1.0a1` is an alpha candidate, not yet a published PyPI release.

The emitted wire format remains `argbridge-v1` for accepted schemas. This release additionally rejects oversized expanded schemas and oversized bundles. Before 1.0, public APIs may change with explicit changelog entries. No JavaScript port, async runtime or full Agents/Mastra integration is shipped.
