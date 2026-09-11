from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hotwash import __version__
from hotwash.detectors import run_all
from hotwash.ingest import load
from hotwash.report import render_md, render_text, to_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hotwash",
        description="After-action review for a coding-agent session. Local, no cloud.",
    )
    p.add_argument("path", nargs="?", help="Grok session directory or JSONL trace")
    p.add_argument("--format", choices=["text", "md", "json"], default="text")
    p.add_argument("-o", "--out", help="Write the report to this file")
    p.add_argument("--version", action="version", version=f"hotwash {__version__}")
    args = p.parse_args(argv)

    if not args.path:
        p.print_help()
        return 2

    try:
        trace = load(args.path)
    except (FileNotFoundError, ValueError) as e:
        print(f"hotwash: {e}", file=sys.stderr)
        return 2

    findings = run_all(trace)
    if args.format == "json":
        body = json.dumps(to_json(trace, findings), indent=2) + "\n"
    elif args.format == "md":
        body = render_md(trace, findings)
    else:
        body = render_text(trace, findings)

    if args.out:
        Path(args.out).write_text(body)
    else:
        sys.stdout.write(body)

    if any(f.severity == "error" for f in findings):
        return 1
    return 0
