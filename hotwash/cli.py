from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from hotwash import __version__
from hotwash.detectors import REGISTRY, run_all
from hotwash.discover import grok_sessions, latest_grok_session
from hotwash.ingest import load
from hotwash.report import render_md, render_text, to_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hotwash",
        description="After-action review for a coding-agent session. Local, no cloud.",
    )
    p.add_argument("path", nargs="?", help="Grok session directory or JSONL trace")
    p.add_argument("--latest", action="store_true", help="Review the newest Grok session")
    p.add_argument("--list", action="store_true", dest="list_sessions", help="List Grok sessions, newest first")
    p.add_argument("--format", choices=["text", "md", "json"], default="text")
    p.add_argument("-o", "--out", help="Write the report to this file")
    p.add_argument(
        "--detectors",
        help="Comma-separated detector names (default: all). Available: " + ", ".join(REGISTRY),
    )
    p.add_argument("--version", action="version", version=f"hotwash {__version__}")
    args = p.parse_args(argv)

    if args.list_sessions:
        return _list()

    path = args.path
    if args.latest:
        try:
            path = str(latest_grok_session())
        except FileNotFoundError as e:
            print(f"hotwash: {e}", file=sys.stderr)
            return 2
    if not path:
        p.print_help()
        print("\nTip: hotwash --list    or    hotwash --latest", file=sys.stderr)
        return 2

    names = None
    if args.detectors:
        names = [n.strip() for n in args.detectors.split(",") if n.strip()]

    try:
        trace = load(path)
        findings = run_all(trace, names)
    except (FileNotFoundError, ValueError) as e:
        print(f"hotwash: {e}", file=sys.stderr)
        return 2

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


def _list() -> int:
    sessions = grok_sessions()
    if not sessions:
        print("hotwash: no Grok sessions found", file=sys.stderr)
        return 2
    for path in sessions:
        mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        print(f"{mtime}  {path}")
    return 0
