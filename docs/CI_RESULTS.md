# Hosted CI verification

On 29 October 2026, [run 40846877084](https://github.com/hans992/ArgBridge/actions/runs/40846877084) completed successfully for commit `3f4eadf5139c44099a8eb48c27682a3e434d38ec` on `release/0.1.0a1`. All **13 expected jobs** passed; none was skipped or cancelled. [Machine-readable checkpoint](../bench/results/release-0.1.0a1/ci-checkpoint.json).

This page records that exact checkpoint. Any later commit needs its own successful run before release; the [branch's Actions history](https://github.com/hans992/ArgBridge/actions?query=branch%3Arelease%2F0.1.0a1) shows current results.

## What passed

- **Ten core matrix jobs:** Windows and Ubuntu, CPython 3.11 through 3.15. Each passed 81 tests, the quickstart and the offline OpenAI request preview.
- **Minimum dependencies:** Ubuntu/Python 3.11 with jsonschema 4.23.0 and referencing 0.35.1; 81 core tests passed.
- **Offline evaluation:** Ubuntu/Python 3.12, pinned Python and Node dependencies; 29 evaluation tests passed and the 995-request plan was prepared with **zero live requests**.
- **Packaging:** Ruff lint/format, source-distribution build, wheel built from that source, strict Twine metadata checks, package scope/secret-pattern checks, clean wheel installation and isolated import/CLI smoke checks passed. The built distributions were retained as temporary Actions artifacts, not published as a package or GitHub Release.

Ubuntu patch versions were 3.11.17, 3.12.15, 3.13.17, 3.14.9 and 3.15.1. Windows patch versions were 3.11.9, 3.12.10, 3.13.16, 3.14.9 and 3.15.1. The checkpoint records each job's observed version and pytest summary. Repeated runs across environments are compatibility evidence; they are not independent model-accuracy samples.

## Initial failure and repair

[Run 40846366009](https://github.com/hans992/ArgBridge/actions/runs/40846366009) at `fa0b53e` failed during workflow validation, before any jobs started. The tokenizer-cache variable used `runner.temp` in job-level `env`, where that context is unavailable. The correction writes the cache path to `GITHUB_ENV` from a runner step using `RUNNER_TEMP`.

Local YAML parsing had passed, demonstrating why syntax parsing alone was insufficient. The corrected file also passed official actionlint 1.7.12, with optional external shellcheck/pyflakes integrations disabled. The checksum of the downloaded Windows actionlint archive was verified against the official release metadata before execution.

## Limits

These checks exercise deterministic code and mocked SDK responses. They do not establish provider acceptance of the new example, model intent accuracy, production suitability, security against every attack or behavior on macOS/alternative interpreters. No model-provider credentials were supplied to CI and no paid inference or deployment ran. Historical real-model measurements and their negative comparison remain unchanged.

The workflow has read-only repository permissions, uses actions pinned by commit, and contains no deployment or package-publication steps. The 35 preserved historical evidence files retain their SHA-256 hashes. A successful workflow is a release prerequisite, not approval to merge, tag, publish or deploy.
