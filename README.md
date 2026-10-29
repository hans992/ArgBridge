# ArgBridge

Preserve **omitted**, **null** and **present** JSON arguments when a strict AI tool schema requires every field.

For a patch-style API, these can be three different operations:

```python
{}                   # retain the existing name
{"name": None}       # clear the name
{"name": "Grace"}    # replace the name
```

Making every optional field nullable can collapse the first two cases. ArgBridge compiles a supported subset of JSON Schema into an explicit wire representation and reconstructs the original JSON after validation. Typed dictionaries are transported as key/value entries, with duplicate keys rejected.

**Experimental alpha: 0.1.0a1 release candidate.** The candidate is prepared locally; it is not yet a published PyPI package. The current public research snapshot and its evidence remain available. No production-readiness or model-accuracy improvement is claimed.

[API](docs/API.md) · [Supported schemas](docs/SUPPORTED_SCHEMAS.md) · [Architecture](docs/ARCHITECTURE.md) · [Compatibility](docs/COMPATIBILITY.md) · [MIT license](LICENSE)

## Try it in five minutes

From a checkout or extracted source archive, create a virtual environment:

```sh
python -m venv .venv
```

On Windows (PowerShell):

```powershell
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python examples/quickstart.py
.venv/Scripts/python -m argbridge --version
```

On macOS/Linux:

```sh
.venv/bin/python -m pip install -e .
.venv/bin/python examples/quickstart.py
.venv/bin/python -m argbridge --version
```

Expected example output:

```text
keep: {}
clear: {"name":null}
replace: {"name":"Grace"}
```

No model, API key or Node installation is required. Python 3.11+ is required; see the distinction between locally tested and CI-targeted versions in [compatibility](docs/COMPATIBILITY.md).

## Python API

```python
from argbridge import Compiled

codec = Compiled({
    "type": "object",
    "properties": {"name": {"type": ["string", "null"]}},
    "additionalProperties": False,
})

keep = codec.encode({})
clear = codec.encode({"name": None})
assert keep != clear
assert codec.decode(keep) == {}
assert codec.decode(clear) == {"name": None}
```

For model-generated arguments, provide `codec.wire_schema` as the tool parameters, then call `codec.decode(loads(argument_text))` using `argbridge.loads`. `encode` transforms existing JSON; it does not infer natural-language intent. Your application defines what null means and decides whether to apply a decoded proposal.

The [OpenAI example](docs/OPENAI_EXAMPLE.md) previews a real Responses request offline. Explicit live opt-in is available with user-supplied credentials; the example never applies changes to an external system. The [in-memory demonstration](examples/demo.py) shows retention, clearing and validation rejection.

## When to use it

ArgBridge may be useful when an integration specifically requires strict closed-object tool schemas while the original contract distinguishes omission from explicit null or uses typed dictionary keys. It supplies reusable compilation and validation for that bounded contract.

For a few stable tools, an explicit handwritten operation wrapper may be simpler. If non-strict tools with local validation are acceptable, start there: that control performed better in the published model experiment. Framework-native validation may already meet your needs. ArgBridge is not a general JSON Schema converter or an agent framework.

## Tradeoffs and evidence

- The original deterministic corpus passed 40 exact round trips, rejected 36 invalid inputs and 12 hostile payloads, and exercised 87 external assertions. **256 external assertions were excluded** as unsupported.
- Aggregate schema size grew from 1,611 to 8,305 UTF-8 bytes: **5.16x**. The experimental factoring variant reduced this to 4.67x; it is not the default codec.
- In **995 real API requests**, all 35 schema probes were accepted. Exact intent accuracy was **91.1%** for ArgBridge, **92.3%** for factored ArgBridge and **96.4%** for original non-strict tools with validation. Original ArgBridge cost 46% more per correct intent in that run.
- The earlier handwritten baseline had an insufficiently documented nested mapping. A revised explicit-path control is now checked offline; **it has no measured live model accuracy**.
- Successful decoding does not establish that a model chose the intended action. The live corpus includes valid but wrong clears and redundant writes.

[Historical benchmark](docs/BENCHMARK.md) · [Full live results and limitations](docs/REALWORLD_EVALUATION.md) · [Current SDK comparison](docs/SDK_COMPARISON.md) · [Release review](docs/RELEASE_REVIEW.md)

Historical measurements name their exact commit, dependencies, corpus and model. The new release adapter and resource checks are not retroactively claimed to have been used in that experiment.

## CLI

```sh
argbridge compile source-schema.json --out bundle.json
argbridge encode bundle.json source-arguments.json --out wire.json
argbridge decode bundle.json wire.json
```

The CLI is offline, reads bounded UTF-8 JSON and reports expected errors as structured JSON with exit code 2. Bundles are recompiled and checked on load. [API and error reference](docs/API.md).

## Scope and security

The supported subset includes primitives, scalar enums, typed arrays, closed objects, typed maps and selected local references/unions. Recursive or remote schemas, patterns/formats and many other keywords are explicitly refused. Source, generated wire and bundle sizes have documented limits. [Complete scope](docs/SUPPORTED_SCHEMAS.md).

Validation is not authentication, authorization, prompt-injection defense or transaction safety. `guarded_call` only validates before invoking your handler. [Security policy](SECURITY.md).

## Develop and contribute

```sh
python -m pip install -e ".[test]"
python -m pytest -m "not evaluation" -q
```

[Reproduction and packaging](docs/REPRODUCING.md) explains the separate optional SDK environment, immutable historical evidence and new output directories. CI is prepared for Windows/Linux and CPython 3.11–3.15; hosted results are pending publication approval, so no passing badge is displayed.

See [CONTRIBUTING](CONTRIBUTING.md), the [code of conduct](CODE_OF_CONDUCT.md) and [changelog](CHANGELOG.md). Reports should contain minimal synthetic schemas and clear expected behavior. Credentials, customer data and private planning do not belong in the repository.

MIT licensed. Vendored test data retains its own attribution; see [dependency and data notices](docs/DEPENDENCIES.md).
