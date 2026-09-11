from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hotwash.model import Message, ToolCall, Trace


def load_generic(path: str | Path) -> Trace:
    """JSONL with role/type fields. One object per line."""
    p = Path(path)
    messages: list[Message] = []
    tools_by_id: dict[str, ToolCall] = {}
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
            cid = str(row.get("id") or row.get("tool_call_id") or f"t{n}")
            result = str(row.get("content") or row.get("result") or "")
            outcome = str(row.get("outcome") or "")
            if cid in tools_by_id:
                tools_by_id[cid].result = result
                if outcome:
                    tools_by_id[cid].outcome = outcome
            else:
                args = row.get("arguments")
                if not isinstance(args, str):
                    args = json.dumps(args or {})
                tools_by_id[cid] = ToolCall(
                    id=cid,
                    name=str(row.get("name") or row.get("tool_name") or "tool"),
                    arguments=args,
                    result=result,
                    outcome=outcome,
                )
            continue
        calls: list[ToolCall] = []
        for tc in row.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            args = tc.get("arguments")
            if not isinstance(args, str):
                args = json.dumps(args or {})
            cid = str(tc.get("id") or f"t{n}-{len(calls)}")
            call = tools_by_id.get(cid) or ToolCall(
                id=cid,
                name=str(tc.get("name") or "unknown"),
                arguments=args,
            )
            if cid not in tools_by_id:
                tools_by_id[cid] = call
            calls.append(call)
        content = row.get("content")
        if not isinstance(content, str):
            content = json.dumps(content) if content is not None else ""
        if role:
            messages.append(Message(role=role, content=content, tool_calls=calls))
    return Trace(source=str(p), messages=messages, tools=list(tools_by_id.values()))
