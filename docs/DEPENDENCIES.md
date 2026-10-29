# Dependencies and attribution

Snapshot checked on 29 October 2026. This is an inventory of distribution metadata and retained notices, not a legal opinion or a vulnerability audit.

## Core installation

The wheel contains ArgBridge code and its MIT license, not vendored runtime dependencies. `jsonschema>=4.23,<5` supplies Draft 2020-12 validation. `referencing>=0.35.1,<1` is a direct dependency because the runtime imports its registry and error types to disable remote retrieval. Delegating validation avoids a second partial validator, but also inherits the dependency's numeric behavior and version compatibility risks.

The locally tested current versions are jsonschema 4.26.0 and referencing 0.37.0, both MIT. Their installed runtime dependencies attrs 26.1.0, jsonschema-specifications 2025.9.1 and rpds-py 2026.9.1 report MIT; typing_extensions 4.16.0 reports PSF-2.0. Core tests also passed with the minimum direct versions, jsonschema 4.23.0 and referencing 0.35.1. These two tested combinations do not prove every version allowed by the ranges.

## Optional examples and development

OpenAI Python 3.41.0 reports Apache-2.0. It is optional and not imported by the core package. The evaluation environment separately uses OpenAI Agents 0.24.0 (MIT), tiktoken 0.14.0 (MIT), Mastra schema-compat 1.3.17 (Apache-2.0) and Zod 4.6.5 (MIT). These packages are comparators or example dependencies, not copied into the wheel.

pytest 9.2.0 reports MIT and Hypothesis 6.170.13 reports MPL-2.0; they are test dependencies. The release tools build 1.6.1, setuptools 84.2.1 and Ruff 0.17.3 report MIT; Twine 7.0.0 reports Apache-2.0. Their presence in a development environment does not relicense ArgBridge code. Preserve each dependency's own license if redistributing it.

The [installed evaluation inventory](../bench/results/release-0.1.0a1/dependency-licenses.json) records names, versions, license metadata/classifiers and notice file locations for all 50 non-pip distributions in that environment. npm's [lockfile](../bench/node/package-lock.json) supplies the separate Node dependency graph. Neither inventory is a guarantee that every transitive release is risk-free.

## Vendored test data

Ten selected Draft 2020-12 files come from the [JSON Schema Test Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite). The original MIT notice, copyright 2012 Julian Berman, remains in [bench/external/LICENSE](../bench/external/LICENSE). [SOURCES.json](../bench/external/SOURCES.json) records retrieval dates, upstream paths and Git blob identities. The benchmark records SHA-256 input hashes and explicit unsupported exclusions. These files are included in the source distribution for reproduction and excluded from the runtime wheel.

The other workflow fixtures and the natural-language corpus are synthetic project data. The historical published provider records omit opaque response/call identifiers and retain synthetic arguments, usage and scores. Private credentials and raw local runs are excluded from release packaging.

## Project license and name

Retain the existing [MIT license](../LICENSE), copyright 2026 hans992. This is the recommended license for owner approval of the alpha release; no relicensing of the prior public snapshot is proposed.

On 29 October 2026, the public PyPI JSON endpoints for `argbridge` and `argbridge-experiment` returned 404. That is only a naming check, not a reservation, trademark clearance or guarantee that an upload will be accepted. Recheck the normalized package name immediately before any separately approved publication. Nothing in the release scripts uploads a package.
