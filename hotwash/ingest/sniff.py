from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def first_objects(path: Path, n: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        if len(rows) >= n:
            break
    return rows


def sniff_file(path: Path) -> str:
    """Return 'claude', 'generic', or 'empty'."""
    rows = first_objects(path)
    if not rows:
        return "empty"
    for row in rows:
        msg = row.get("message")
        if (
            row.get("type") in {"user", "assistant"}
            and isinstance(msg, dict)
            and (msg.get("role") in {"user", "assistant"} or "content" in msg)
        ):
            return "claude"
    return "generic"


def sniff_session_id(rows: list[dict[str, Any]]) -> Optional[str]:
    for row in rows:
        sid = row.get("sessionId") or row.get("session_id")
        if sid:
            return str(sid)
    return None
