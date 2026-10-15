"""Command-line interface: ``llmjson [file|-]``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .extract import LLMJSONError, extract_all, find, loads
from .repair import repair


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmjson",
        description="Extract and repair JSON from messy LLM output "
        "(markdown fences, <think> tags, prose, trailing commas, truncation).",
        epilog="exit status: 0 = JSON recovered, 1 = no JSON could be recovered, 2 = usage error",
    )
    p.add_argument("file", nargs="?", default="-", help="input file (default: stdin, or '-')")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("-i", "--indent", type=int, default=2, metavar="N", help="pretty-print with N spaces (default 2)")
    fmt.add_argument("-r", "--raw", action="store_true", help="print compact single-line JSON")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--repair-only", action="store_true",
                      help="print the extracted snippet after repair, without parsing it")
    mode.add_argument("--find", action="store_true", help="print the extracted snippet as-is (no repair, no parse)")
    mode.add_argument("-a", "--all", action="store_true", help="print every JSON value found, one per line (JSONL)")
    p.add_argument("-s", "--strict", action="store_true", help="refuse to repair; only extract valid JSON")
    p.add_argument("--ascii", action="store_true", help="escape non-ASCII characters in the output")
    p.add_argument("-V", "--version", action="version", version="llmjson " + __version__)
    return p


def _read(path: str) -> str:
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(path, "rb") as fh:
            data = fh.read()
    return data.decode("utf-8", errors="replace")


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        text = _read(args.file)
    except OSError as e:
        print("llmjson: %s" % e, file=sys.stderr)
        return 1

    dump_kw = {"ensure_ascii": args.ascii}
    if args.raw or args.all:
        dump_kw["separators"] = (",", ":")
    else:
        dump_kw["indent"] = args.indent

    try:
        if args.repair_only or args.find:
            try:
                snippet = find(text, strict=args.strict)
            except LLMJSONError:
                if args.find:
                    raise
                snippet = text.strip()
            sys.stdout.write((repair(snippet) if args.repair_only else snippet) + "\n")
            return 0
        if args.all:
            values = extract_all(text, strict=args.strict)
            if not values:
                raise LLMJSONError("no JSON object or array found in input")
            for v in values:
                sys.stdout.write(json.dumps(v, **dump_kw) + "\n")
            return 0
        value = loads(text, strict=args.strict)
    except LLMJSONError as e:
        print("llmjson: %s" % e, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(value, **dump_kw) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
