# Contributing

ArgBridge is an experimental Python codec for presence-sensitive tool arguments. Contributions that improve correctness, usability and evidence are welcome. A small, demonstrated improvement is more useful than another framework adapter without tests.

## Local setup

Use Python 3.11 or newer in a virtual environment. Install the checkout with `python -m pip install -e ".[test]"`, then run `python -m pytest -m "not evaluation"` and `python examples/quickstart.py`. No API key or Node installation is needed for core tests.

The optional SDK evaluation uses the separate locked environment described in [benchmark reproduction](docs/REPRODUCING.md). It requires Node and a cached tokenizer, but its tests still make no inference calls. Never run paid inference as part of a contribution without the account owner's authorization.

## A useful change

1. Describe a reproducible problem, including the source schema, input, expected result and installed versions. Use synthetic data.
2. Add a regression that fails for the demonstrated bug. For a new schema feature, cover both valid values and hostile wire data.
3. Keep the original-schema validation boundary. Do not silently coerce values, drop keys, conflate missing with null, or resolve remote references.
4. Run relevant tests. Record provider-generated evidence separately from deterministic results.
5. Explain compatibility and overhead changes in the pull request and changelog.

The runtime is in `src/argbridge`; examples are executable scripts; `bench` contains deterministic comparisons; `evals/realworld` preserves a frozen model experiment. The public API is `Compiled`, the two error classes, JSON helpers and the CLI. `argbridge-v1` is a serialized wire format, not a version of the Python distribution.

Do not overwrite historical data in `bench/results` or the frozen dataset/live artifacts. Write new measurements to a separate directory, record dependencies and corpus hashes, and explain changes. The improved manual wrapper is a separate comparator, not a retroactive change to the live experiment.

Use Ruff for the runtime and new examples (`python -m ruff check src examples` and `python -m ruff format --check src examples`). Prefer readable Python and a small dependency surface. Discuss significant public API or wire-format changes before implementation.

Contributions are accepted under the project's existing MIT license. Retain third-party attribution. Do not include credentials, customer data, private chats or internal planning. Follow the [code of conduct](CODE_OF_CONDUCT.md) and use the [security policy](SECURITY.md) for vulnerabilities.
