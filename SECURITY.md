# Security policy

ArgBridge is experimental. Only the current alpha is a maintenance target; there is no production support or incident-response SLA.

## Reporting

Use the repository's **Security → Report a vulnerability** flow if private vulnerability reporting is enabled. If it is unavailable, ask the owner for a private reporting channel in a minimal issue without exploit details, credentials, customer information or private data. The release checklist asks the owner to enable private reporting before publication; this document does not assume that setting is enabled.

Provide the version, a minimal synthetic schema/input, expected rejection, observed behavior and affected boundary. Do not test against other users' systems. Do not post active credentials or production payloads.

## Boundaries

- Schemas are application configuration and should be trusted. Inputs are ordinary JSON; Python objects with custom behavior are rejected by the codec's JSON checks.
- The codec bounds JSON data, source and generated wire schemas. CLI input files are read through a byte limit. Expanded references are limited; remote retrieval and recursive references are refused.
- A bundle hash detects mismatches. It is not a signature, identity proof or trust assertion. Recompilation validates its contents; it does not make an attacker-supplied schema an authorized application contract.
- Decode validates wire data, rejects duplicate/colliding map entries and validates the reconstructed JSON against the original schema. This boundary is not authentication, authorization, intent checking, prompt-injection prevention, transaction isolation or a sandbox.
- `guarded_call` invokes the supplied handler once after validation. It does not undo effects, make calls idempotent or stop a handler from using the network/filesystem. Handler errors propagate.
- Error details avoid argument values, but JSON Pointer paths can contain user-provided keys. Treat logs accordingly.
- Bounds reduce accidental and adversarial work; they are not a complete denial-of-service guarantee. Dependency validators and Python numeric behavior remain part of the trusted runtime.

The OpenAI example proposes a patch for review and never applies it. Its live mode needs explicit opt-in and a caller-supplied environment key; retries are disabled. Provider schema acceptance does not establish safe intent. The [live experiment](docs/REALWORLD_EVALUATION.md) contains accepted but incorrect model-generated patches.
