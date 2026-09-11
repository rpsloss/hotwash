from __future__ import annotations

from pathlib import Path

from hotwash.detectors import run_all
from hotwash.ingest import load
from hotwash.ingest.sniff import sniff_file
from hotwash.report import rank


def _guess_kind(path: Path) -> str:
    if path.is_dir():
        if (path / "chat_history.jsonl").exists() or (path / "events.jsonl").exists():
            return "grok"
        try:
            kids = [
                c
                for c in path.iterdir()
                if c.is_dir() and (c / "chat_history.jsonl").exists()
            ]
        except OSError:
            return "generic"
        if kids:
            return "grok"
        jsonl = sorted(path.glob("*.jsonl"))
        if len(jsonl) == 1:
            return _guess_kind(jsonl[0])
        return "generic"
    if path.is_file():
        kind = sniff_file(path)
        if kind in {"claude", "codex", "cursor"}:
            return kind
        return "generic"
    name = path.name
    if name.startswith("rollout-") and name.endswith(".jsonl"):
        return "codex"
    if name == "chat_history.jsonl":
        return "grok"
    return "generic"


def _clip(text: str, n: int = 80) -> str:
    text = " ".join((text or "").split())
    return text[:n]


def _error_row(path: Path, kind: str) -> dict:
    return {
        "path": str(path),
        "kind": kind,
        "session_id": None,
        "user_turns": 0,
        "tools": 0,
        "rank": "ERROR",
        "detectors": [],
        "prompt": "",
    }


def session_preview(path: Path) -> dict:
    """Load a session and return a one-line list summary (rank, detectors, prompt)."""
    p = Path(path).expanduser()
    kind = _guess_kind(p)
    try:
        trace = load(p)
    except Exception:
        return _error_row(p, kind)
    findings = run_all(trace)
    label, _ = rank(findings)
    first = next((m.content for m in trace.messages if m.role == "user"), "")
    return {
        "path": str(p),
        "kind": kind,
        "session_id": trace.session_id,
        "user_turns": sum(1 for m in trace.messages if m.role == "user"),
        "tools": len(trace.tools),
        "rank": label,
        "detectors": list(
            dict.fromkeys(f.detector for f in findings if f.severity == "error")
        ),
        "prompt": _clip(first, 80),
    }
