from __future__ import annotations

from pathlib import Path

from hotwash.ingest.claude import load_claude
from hotwash.ingest.codex import load_codex
from hotwash.ingest.cursor import load_cursor
from hotwash.ingest.generic import load_generic
from hotwash.ingest.grok import load_grok
from hotwash.ingest.sniff import sniff_file
from hotwash.model import Trace


def load(path: str | Path) -> Trace:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    if p.is_dir():
        if (p / "chat_history.jsonl").exists() or (p / "events.jsonl").exists():
            return load_grok(p)
        kids = [c for c in p.iterdir() if c.is_dir() and (c / "chat_history.jsonl").exists()]
        if len(kids) == 1:
            return load_grok(kids[0])
        if kids:
            raise ValueError(
                f"{p} has {len(kids)} session dirs. Pass one of them:\n"
                + "\n".join(f"  {c}" for c in kids)
            )
        jsonl = sorted(p.glob("*.jsonl"))
        if len(jsonl) == 1:
            return load(jsonl[0])
        raise ValueError(f"No chat_history.jsonl under {p}")
    kind = sniff_file(p)
    if kind == "claude":
        return load_claude(p)
    if kind == "cursor":
        return load_cursor(p)
    if kind == "codex":
        return load_codex(p)
    return load_generic(p)
