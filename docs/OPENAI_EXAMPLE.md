# OpenAI strict function-calling example

Install the checkout, then run the default offline preview:

```sh
python -m pip install -e .
python examples/openai_tool.py
```

It prints a Responses request using `codec.wire_schema` as the strict function parameters. It makes no request and reads no credential. The tool is `propose_contact_update`, because even valid decoded arguments require application review before effects.

For a self-authorized live request, install the optional SDK and supply your own `OPENAI_API_KEY` in the environment using your normal local secret-management method. Do not put keys in source, issues or command history. The script does not read `.env`, ChatGPT login state or other projects' credentials.

```sh
python -m pip install -e ".[openai]"
python examples/openai_tool.py --live --allow-paid-inference
```

This sends one billable request to the official global OpenAI endpoint with retries disabled, a 30-second timeout and a 512-output-token limit. API billing is separate from a ChatGPT subscription. A token limit is not an account spending cap; check current [model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini) before opting in. This release preparation did not execute the example's live mode.

The default model is `gpt-5.4-mini-2026-03-17`; `--model` is explicit and other models may require different settings. The example uses clear, unambiguous instructions. It is not a general agent loop and deliberately does not retry, follow up, authorize users or mutate an external system.

Responses must be complete and contain exactly one call to the expected tool. Raw arguments pass through ArgBridge's duplicate-aware `loads`, wire validation, decoding and original-contract validation. The output labels the result as a proposal, includes reported usage and sets `applied: false`. Incorrect intent can still pass all of those checks.

Tests use synthetic responses and a mocked SDK transport. They establish adapter behavior only. The separate [995-request experiment](REALWORLD_EVALUATION.md) contains real provider evidence for its frozen schemas and settings, including intent failures. Do not transfer that compatibility claim to this new example without running it.

See the official [function-calling guide](https://developers.openai.com/api/docs/guides/function-calling) for the all-properties-required/closed-object strict contract. The library does not claim to replace application-specific schema design, validation or a careful manual wrapper.
