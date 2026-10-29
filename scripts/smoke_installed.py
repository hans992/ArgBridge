"""Run with python -I after installing the built wheel, outside an editable environment."""

from pathlib import Path
import json
import subprocess
import sys

import argbridge
from argbridge import Compiled

assert "site-packages" in Path(argbridge.__file__).parts, "Smoke check must use an installed wheel"
codec = Compiled(
    {
        "type": "object",
        "properties": {"name": {"type": ["string", "null"]}},
        "additionalProperties": False,
    }
)
for value in ({}, {"name": None}, {"name": "Grace"}):
    assert codec.decode(codec.encode(value)) == value
cli = subprocess.run(
    [sys.executable, "-I", "-m", "argbridge", "--version"],
    check=True,
    capture_output=True,
    text=True,
)
assert cli.stdout.strip() == "argbridge " + argbridge.__version__
print(
    json.dumps(
        {
            "version": argbridge.__version__,
            "installed_wheel_import": True,
            "presence_roundtrips": 3,
            "cli_version": "passed",
        }
    )
)
