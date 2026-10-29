# Changelog

## 0.1.0a1 — experimental alpha (2026-10-29)

Initial developer-facing experimental alpha, released as the [v0.1.0a1 GitHub prerelease](https://github.com/hans992/ArgBridge/releases/tag/v0.1.0a1). The package version remains `0.1.0a1`; this is not a PyPI publication or a production-readiness claim.

### Fixed

- Bound expanded wire schemas after compilation; previously a small source with repeated long descriptions could exceed the JSON budget.
- Check serialized bundles against their own reader's budget before returning them.
- Bound CLI file reads before parsing and make non-ASCII JSON output usable on legacy Windows consoles.
- Keep serialized CLI output inside the reader's byte limit, including formatting, ASCII escaping and any trailing newline; use compact JSON near the limit and reject oversized stdout output before emission.
- Declare the directly imported `referencing` dependency explicitly.
- Escape unsupported keyword names correctly in JSON Pointer error paths.
- Initialize the CI tokenizer cache inside a runner step; the runner context is unavailable in job-level environment expressions.

### Added

- Distribution name `argbridge`, a single version source, `python -m argbridge`, and `argbridge --version`.
- Five-minute quickstart, offline-first OpenAI Responses proposal example and adapter regressions.
- Explicit-path manual comparator, including empty nested/map patches; no live inference results are claimed for it.
- Contribution/security policies, CI, issue/PR templates, compatibility/API documentation and release checks.
- Benchmarks write to separate directories by default instead of replacing historical evidence.

### Evidence retained

The original codec experiment's 5.16x schema-byte expansion and all unsupported cases remain documented. The prior 995-request live evaluation still shows lower accuracy and higher cost than the original non-strict control for that corpus. Its dataset, results and baseline code remain frozen; those measurements are not attributed to this release's new adapter or revised manual comparator.

The wire representation remains `argbridge-v1` for schemas that fit the resource limits. There is no claim of API stability before 1.0, universal JSON Schema support or production-ready model intent.
