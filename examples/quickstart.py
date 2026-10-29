"""Run after installing ArgBridge. No model, credentials or network required."""

from argbridge import Compiled, canonical

codec = Compiled(
    {
        "type": "object",
        "properties": {"name": {"type": ["string", "null"]}},
        "additionalProperties": False,
    }
)

for label, patch in (("keep", {}), ("clear", {"name": None}), ("replace", {"name": "Grace"})):
    restored = codec.decode(codec.encode(patch))
    assert restored == patch
    print(label + ": " + canonical(restored))

assert codec.encode({}) != codec.encode({"name": None})
