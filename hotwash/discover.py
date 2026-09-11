from __future__ import annotations

from pathlib import Path


def default_grok_root() -> Path:
    return Path.home() / ".grok" / "sessions"


def grok_sessions(root: Path | None = None) -> list[Path]:
    """Newest-first Grok session dirs that contain chat_history.jsonl."""
    base = Path(root) if root is not None else default_grok_root()
    if not base.exists():
        return []
    found: list[Path] = []
    for hist in base.rglob("chat_history.jsonl"):
        found.append(hist.parent)
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found


def latest_grok_session(root: Path | None = None) -> Path:
    sessions = grok_sessions(root)
    if not sessions:
        raise FileNotFoundError(
            f"No Grok sessions with chat_history.jsonl under {root or default_grok_root()}"
        )
    return sessions[0]
