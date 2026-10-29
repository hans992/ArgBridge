# Reproducing tests and benchmarks

Use separate environments for core development, current SDK evaluation and the historical benchmark. None of the commands below invokes paid inference. Dependency installation and tokenizer downloads use the network.

## Core checks

From a checkout, create and activate a virtual environment using `python -m venv .venv` and your platform's activation command, or invoke `.venv/Scripts/python` on Windows / `.venv/bin/python` on Unix explicitly.

```sh
python -m pip install -e ".[test]"
python -m pytest -m "not evaluation" -q
python examples/quickstart.py
python examples/openai_tool.py
```

The minimal suite includes fixed contracts, property-based tests, hostile inputs, resource regressions, CLI behavior and the manual comparator. It does not require OpenAI, Node or an API key.

## Optional SDK tests and a new offline plan

In a separate environment:

```sh
python -m pip install -r evals/realworld/requirements-lock.txt
python -m pip install --no-build-isolation --no-deps -e .
npm --prefix bench/node ci --ignore-scripts --no-audit --no-fund
python -c "import tiktoken; tiktoken.encoding_for_model('gpt-5.4-mini-2026-03-17')"
python -m pytest -q
python -m evals.realworld.harness prepare --output evals/realworld/runs/prepared-new
```

The public tokenizer data must be cached before tests, because inference-oriented tests block socket connections. `TIKTOKEN_CACHE_DIR` can select the cache. `ARGBRIDGE_NODE_BIN` can specify Node if it is not on PATH.

Preparation requires a fresh output directory. It writes a disabled authorization template and a plan bound to the current source, dependencies and unchanged dataset. The revised explicit-path manual comparator in `bench/manual_wrapper.py` is evaluated separately offline; the six-arm historical harness still names the original manual arm. Do not label its old model scores as measurements of the revised wrapper.

Live execution, if separately authorized by the API account owner, requires an explicit `--plan`, a matching approval file, `--allow-spend`, a finite budget, credentials and a fresh run directory. No CI job runs live mode. The original approval from the historical experiment is single-use and does not authorize another run.

## Current deterministic benchmark

With the evaluation environment and npm dependencies installed:

```sh
node bench/node/compare.mjs bench/results/local-rerun
python bench/run.py --output bench/results/local-rerun
python bench/release_compare.py --output bench/results/local-rerun/manual-comparison.json
```

The output includes corpus hashes, versions, exclusions, schema byte counts and compile/encode/decode timings. Compile and warmup are excluded from the measured encode+decode loop. Run on an otherwise idle machine; filesystem activity and scheduling can affect tails. The default output is separate from historical results, and the runner refuses the historical root directory.

The benchmark's two simple normalization baselines are explanatory controls, not the strongest alternatives. The [current SDK review](SDK_COMPARISON.md), frozen non-strict/manual comparisons and revised explicit-path comparator provide the additional context. SDK helper results are not full framework integration tests.

## Historical results

The original files under `bench/results` and `evals/realworld/artifacts` remain unchanged. The complete pre-release research snapshot is commit `a9cd459c8cd58624af8102e1dc714c81678a79f9`. To reproduce its exact code and plan hashes, use a separate checkout of that commit; running new source cannot reproduce an old source hash.

The historical offline benchmark uses `bench/requirements-lock.txt`, Node dependencies from `bench/node/package-lock.json`, `node bench/node/compare.mjs`, `python bench/run.py` and `python -m pytest tests/test_contracts.py`. Those older scripts write into their checkout's `bench/results`, so use a disposable checkout.

For the historical live analysis, install `evals/realworld/requirements-lock.txt` in another environment and run the old commit's `python -m evals.realworld.harness prepare` to reconstruct its plan. Then run its `evals/realworld/analysis/report.py` against the published records. This recomputes analysis, not model output. A new model run may vary even at temperature zero.

## Build and inspect

```sh
python -m pip install build==1.6.1 setuptools==84.2.1 twine==7.0.0
python -m build --no-isolation
python -m twine check --strict dist/*
python scripts/check_release.py dist
```

On shells that do not expand globs, pass the two distribution filenames explicitly to Twine. Install the wheel in a fresh environment, then run `python -I scripts/smoke_installed.py` to verify the installed import and CLI. Do not use an editable installation for that check.

CI additionally tests Windows/Linux CPython 3.11–3.15 and minimum runtime dependency versions. It is read-only, pins actions by commit and has no package-publication or deployment job. The build job uploads temporary test artifacts only. [Hosted results](CI_RESULTS.md) are recorded separately from local verification.

For workflow changes, also run `actionlint -shellcheck= -pyflakes= .github/workflows/ci.yml` using the separately installed official actionlint tool (1.7.12 was verified). YAML parsing alone does not validate GitHub expression contexts. This optional developer tool is not a package dependency; disabling its shellcheck/pyflakes integrations limits the check to actionlint's built-in validation.
