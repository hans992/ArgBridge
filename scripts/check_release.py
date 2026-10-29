"""Inspect locally built distributions. Does not upload or use credentials."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

SECRET = re.compile(
    rb"(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
PRIVATE = (".env", "authorization.local.json", "plan.json", "OPPORTUNITIES.md", "PROGRESS.md")


def inspect(path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            files = {
                name: archive.read(name) for name in archive.namelist() if not name.endswith("/")
            }
        assert all(name.startswith(("argbridge/", "argbridge-")) for name in files)
        assert any(name.endswith("/licenses/LICENSE") for name in files)
        assert "argbridge/__main__.py" in files
    else:
        with tarfile.open(path, "r:gz") as archive:
            assert not any(m.issym() or m.islnk() for m in archive.getmembers())
            files = {
                m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()
            }
        assert any(name.endswith("/bench/external/LICENSE") for name in files)
        assert any(name.endswith("/examples/openai_tool.py") for name in files)
    for name, data in files.items():
        parts = PurePosixPath(name).parts
        assert ".." not in parts and not name.startswith("/")
        assert not any(
            part in PRIVATE or part in (".git", "node_modules", "__pycache__", "runs")
            for part in parts
        ), name
        assert not SECRET.search(data), "Possible credential in " + name
        assert b"C:" + b"\\Users\\" not in data and b"C:" + b"/Users/" not in data, (
            "Local user path in " + name
        )
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "entries": len(files),
        "scope_and_secret_pattern_checks": "passed",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    packages = sorted(args.directory.glob("*.whl")) + sorted(args.directory.glob("*.tar.gz"))
    if not packages:
        parser.error("No wheel or source distribution found")
    print(json.dumps([inspect(path) for path in packages], indent=2))
