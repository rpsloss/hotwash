from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hotwash.model import Message, ToolCall, Trace


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif "text" in item:
                    parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        return str(content.get("text") or json.dumps(content))
    return str(content)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_grok(session_dir: str | Path) -> Trace:
    d = Path(session_dir)
    history = _read_jsonl(d / "chat_history.jsonl")
    events = _read_jsonl(d / "events.jsonl")

    outcomes: dict[str, dict[str, str]] = {}
    for ev in events:
        if ev.get("type") != "tool_completed":
            continue
        cid = str(ev.get("tool_call_id") or "")
        if not cid:
            continue
        outcomes[cid] = {
            "outcome": str(ev.get("outcome") or ""),
            "ts": str(ev.get("ts") or ""),
        }

    tools_by_id: dict[str, ToolCall] = {}
    messages: list[Message] = []
    pending_results: dict[str, str] = {}

    for row in history:
        kind = row.get("type")
        if kind == "user":
            messages.append(
                Message(role="user", content=_flatten_content(row.get("content")), ts=str(row.get("ts") or ""))
            )
        elif kind == "assistant":
            calls: list[ToolCall] = []
            for tc in row.get("tool_calls") or []:
                cid = str(tc.get("id") or "")
                args = tc.get("arguments")
                if not isinstance(args, str):
                    args = json.dumps(args or {})
                call = ToolCall(
                    id=cid,
                    name=str(tc.get("name") or "unknown"),
                    arguments=args,
                    result=pending_results.pop(cid, ""),
                    outcome=outcomes.get(cid, {}).get("outcome", ""),
                    ts=outcomes.get(cid, {}).get("ts", ""),
                )
                tools_by_id[cid] = call
                calls.append(call)
            messages.append(
                Message(
                    role="assistant",
                    content=_flatten_content(row.get("content")),
                    tool_calls=calls,
                    ts=str(row.get("ts") or ""),
                )
            )
        elif kind == "tool_result":
            cid = str(row.get("tool_call_id") or "")
            text = _flatten_content(row.get("content"))
            if cid in tools_by_id:
                tools_by_id[cid].result = text
            else:
                pending_results[cid] = text
        elif kind == "system":
            messages.append(
                Message(role="system", content=_flatten_content(row.get("content")), ts=str(row.get("ts") or ""))
            )

    return Trace(
        source=str(d),
        session_id=d.name,
        messages=messages,
        tools=list(tools_by_id.values()),
        events=events,
    )
