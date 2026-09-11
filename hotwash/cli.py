from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from hotwash import __version__
from hotwash.case import eval_dir, render_eval, write_case
from hotwash.detectors import REGISTRY, run_all
from hotwash.discover import all_sessions, grok_sessions, latest_grok_session
from hotwash.ingest import load
from hotwash.report import render_md, render_text, to_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hotwash",
        description="After-action review for a coding-agent session. Local, no cloud.",
    )
    p.add_argument("path", nargs="?", help="Grok session directory or JSONL trace")
    p.add_argument("--latest", action="store_true", help="Review the newest Grok session")
    p.add_argument("--list", action="store_true", dest="list_sessions", help="List Grok and Claude sessions, newest first")
    p.add_argument("--format", choices=["text", "md", "json"], default="text")
    p.add_argument(
        "--dump-trace",
        action="store_true",
        help="Print the normalized trace JSON instead of running detectors",
    )
    p.add_argument(
        "--eval",
        dest="eval_dir",
        metavar="DIR",
        help="Run the portable case suite in DIR (*.jsonl + *.expect.json)",
    )
    p.add_argument(
        "--write-case",
        metavar="STEM",
        help="Freeze this session as STEM.jsonl + STEM.expect.json",
    )
    p.add_argument("-o", "--out", help="Write the report to this file")
    p.add_argument(
        "--detectors",
        help="Comma-separated detector names (default: all). Available: " + ", ".join(REGISTRY),
    )
    p.add_argument("--version", action="version", version=f"hotwash {__version__}")
    args = p.parse_args(argv)

    if args.list_sessions:
        return _list()

    if args.eval_dir:
        try:
            rows = eval_dir(Path(args.eval_dir))
        except (FileNotFoundError, ValueError) as e:
            print(f"hotwash: {e}", file=sys.stderr)
            return 2
        if args.format == "json":
            sys.stdout.write(json.dumps(rows, indent=2) + "\n")
        else:
            sys.stdout.write(render_eval(rows))
        return 0 if all(r["ok"] for r in rows) else 1

    path = args.path
    if args.latest:
        try:
            path = str(latest_grok_session())
        except FileNotFoundError as e:
            print(f"hotwash: {e}", file=sys.stderr)
            return 2
    if not path:
        p.print_help()
        print("\nTip: hotwash --list    or    hotwash --latest    or    hotwash --eval cases", file=sys.stderr)
        return 2

    if path == "-":
        import tempfile

        raw = sys.stdin.read()
        tmp = Path(tempfile.mkdtemp(prefix="hotwash-")) / "stdin.jsonl"
        tmp.write_text(raw)
        path = str(tmp)

    names = None
    if args.detectors:
        names = [n.strip() for n in args.detectors.split(",") if n.strip()]

    try:
        trace = load(path)
    except (FileNotFoundError, ValueError) as e:
        print(f"hotwash: {e}", file=sys.stderr)
        return 2

    if args.dump_trace:
        body = json.dumps(trace.to_dict(), indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(body)
        else:
            sys.stdout.write(body)
        return 0

    try:
        findings = run_all(trace, names)
    except ValueError as e:
        print(f"hotwash: {e}", file=sys.stderr)
        return 2

    if args.write_case:
        jsonl, expect = write_case(trace, findings, Path(args.write_case))
        print(f"wrote {jsonl}", file=sys.stderr)
        print(f"wrote {expect}", file=sys.stderr)

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
    sessions = all_sessions()
    if not sessions:
        grok = grok_sessions()
        if not grok:
            print("hotwash: no Grok or Claude sessions found", file=sys.stderr)
            return 2
    for kind, path in sessions:
        mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        print(f"{mtime}  {kind:6}  {path}")
    return 0
