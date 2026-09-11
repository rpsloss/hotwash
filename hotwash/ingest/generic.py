from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hotwash.model import Message, ToolCall, Trace


def load_generic(path: str | Path) -> Trace:
    """JSONL with role/type fields. One object per line."""
    p = Path(path)
    messages: list[Message] = []
    tools: list[ToolCall] = []
    n = 0
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        n += 1
        role = str(row.get("role") or row.get("type") or "")
        if role in {"tool", "tool_result"}:
            call = ToolCall(
                id=str(row.get("id") or row.get("tool_call_id") or f"t{n}"),
                name=str(row.get("name") or row.get("tool_name") or "tool"),
                arguments=row.get("arguments") if isinstance(row.get("arguments"), str) else json.dumps(row.get("arguments") or {}),
                result=str(row.get("content") or row.get("result") or ""),
                outcome=str(row.get("outcome") or ""),
            )
            tools.append(call)
            continue
        calls: list[ToolCall] = []
        for tc in row.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            args = tc.get("arguments")
            if not isinstance(args, str):
                args = json.dumps(args or {})
            call = ToolCall(
                id=str(tc.get("id") or f"t{n}-{len(calls)}"),
                name=str(tc.get("name") or "unknown"),
                arguments=args,
            )
            calls.append(call)
            tools.append(call)
        content = row.get("content")
        if not isinstance(content, str):
            content = json.dumps(content) if content is not None else ""
        if role:
            messages.append(Message(role=role, content=content, tool_calls=calls))
    return Trace(source=str(p), messages=messages, tools=tools)
