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


def default_claude_root() -> Path:
    return Path.home() / ".claude" / "projects"


def claude_sessions(root: Path | None = None) -> list[Path]:
    """Newest-first Claude Code session JSONL files."""
    base = Path(root) if root is not None else default_claude_root()
    if not base.exists():
        return []
    found: list[Path] = []
    for path in base.rglob("*.jsonl"):
        name = path.name
        if name.startswith("agent-") or name == "chat_history.jsonl":
            continue
        found.append(path)
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found


def all_sessions() -> list[tuple[str, Path]]:
    rows: list[tuple[float, str, Path]] = []
    for path in grok_sessions():
        rows.append((path.stat().st_mtime, "grok", path))
    for path in claude_sessions():
        rows.append((path.stat().st_mtime, "claude", path))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [(kind, path) for _, kind, path in rows]
