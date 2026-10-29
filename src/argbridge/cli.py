"""Offline command line interface; no network, credentials, or automatic tool execution."""

import argparse
import json
from pathlib import Path
import sys
from .core import BridgeError, Compiled, loads
from .core import MAX_BYTES
from ._version import __version__


def read(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise BridgeError("resource_limit", "", "Input file exceeds JSON byte budget")
    return loads(raw.decode("utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"argbridge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    compile_cmd = sub.add_parser("compile", help="Compile source schema into a verifiable bundle")
    compile_cmd.add_argument("schema")
    compile_cmd.add_argument("--out")
    for name in ("encode", "decode"):
        cmd = sub.add_parser(name)
        cmd.add_argument("bundle")
        cmd.add_argument("input")
        cmd.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            result = Compiled(read(args.schema)).bundle()
        else:
            compiled = Compiled.from_bundle(read(args.bundle))
            result = getattr(compiled, args.command)(read(args.input))
        rendered = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_bytes(rendered.encode("utf-8"))
        else:
            # ASCII JSON is valid UTF-8 and also works on legacy Windows consoles.
            print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
    except BridgeError as exc:
        print(json.dumps({"error": exc.as_dict()}), file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        print(
            '{"error":{"code":"io_error","detail":"Unable to read/write UTF-8 file"}}',
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
