from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from hotwash import __version__
from hotwash.case import eval_dir, render_eval, write_case
from hotwash.coverage import coverage, render_coverage
from hotwash.detectors import REGISTRY, run_all
from hotwash.discover import all_sessions, latest_session
from hotwash.ingest import load
from hotwash.redact import redact_obj
from hotwash.report import rank, render_html, render_md, render_text, to_json
from hotwash.summarize import session_preview


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hotwash",
        description="After-action review for a coding-agent session. Local, no cloud.",
    )
    p.add_argument("path", nargs="?", help="Grok session dir, Claude/Codex JSONL, or generic trace")
    p.add_argument("--latest", action="store_true", help="Review the newest Grok, Claude, or Codex session")
    p.add_argument("--list", action="store_true", dest="list_sessions", help="List Grok, Claude, Codex, and Cursor sessions, newest first")
    p.add_argument(
        "--rank",
        action="store_true",
        help="With --list, print rank, error detectors, and first prompt",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1 if any finding)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Print rank and finding lines only",
    )
    p.add_argument("--format", choices=["text", "md", "json", "html"], default="text")
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
        "--coverage",
        dest="coverage_dir",
        metavar="DIR",
        help="Show which detectors have no case in DIR",
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
        return _list(rank_rows=args.rank)

    if args.coverage_dir:
        try:
            data = coverage(Path(args.coverage_dir))
        except (FileNotFoundError, ValueError) as e:
            print(f"hotwash: {e}", file=sys.stderr)
            return 2
        if args.format == "json":
            sys.stdout.write(json.dumps(data, indent=2) + "\n")
        else:
            sys.stdout.write(render_coverage(data))
        return 0 if not data.get("missing") else 1

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
            path = str(latest_session())
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
        body = json.dumps(redact_obj(trace.to_dict()), indent=2) + "\n"
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

    if args.quiet:
        label, _ = rank(findings)
        lines = [f"rank {label}"]
        lines.extend(f.line() for f in findings)
        body = "\n".join(lines) + "\n"
    elif args.format == "json":
        body = json.dumps(to_json(trace, findings), indent=2) + "\n"
    elif args.format == "md":
        body = render_md(trace, findings)
    elif args.format == "html":
        body = render_html(trace, findings)
    else:
        body = render_text(trace, findings)

    if args.out:
        Path(args.out).write_text(body)
    else:
        sys.stdout.write(body)

    if any(f.severity == "error" for f in findings):
        return 1
    if args.strict and findings:
        return 1
    return 0


def _list(*, rank_rows: bool = False) -> int:
    sessions = all_sessions()
    if not sessions:
        print("hotwash: no Grok, Claude, Codex, or Cursor sessions found", file=sys.stderr)
        return 2
    for kind, path in sessions:
        mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if not rank_rows:
            print(f"{mtime}  {kind:6}  {path}")
            continue
        row = session_preview(path)
        dets = ",".join(row.get("detectors") or []) or "-"
        prompt = row.get("prompt") or ""
        print(f"{mtime}  {row.get('rank','?'):8}  {kind:6}  {dets:20}  {prompt}")
    return 0
