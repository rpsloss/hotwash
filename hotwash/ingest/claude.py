from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hotwash.ingest.sniff import first_objects, sniff_session_id
from hotwash.model import Message, ToolCall, Trace


def _text_from_content(content: Any) -> str:
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
                elif item.get("type") == "tool_result":
                    continue
                elif "text" in item:
                    parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        return str(content.get("text") or "")
    return str(content)


def load_claude(path: str | Path) -> Trace:
    """Claude Code session JSONL (type + message.role/content, tool_use / tool_result)."""
    p = Path(path)
    tools_by_id: dict[str, ToolCall] = {}
    messages: list[Message] = []
    session_id = sniff_session_id(first_objects(p)) or p.stem

    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = row.get("type")
        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        content = msg.get("content") if msg else row.get("content")
        ts = str(row.get("timestamp") or row.get("ts") or "")

        if kind == "assistant" or msg.get("role") == "assistant":
            calls: list[ToolCall] = []
            texts: list[str] = []
            blocks = content if isinstance(content, list) else []
            if isinstance(content, str):
                texts.append(content)
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    texts.append(str(block.get("text") or ""))
                elif btype == "tool_use":
                    cid = str(block.get("id") or "")
                    args = block.get("input")
                    if not isinstance(args, str):
                        args = json.dumps(args or {})
                    call = ToolCall(
                        id=cid,
                        name=str(block.get("name") or "unknown"),
                        arguments=args,
                        ts=ts,
                    )
                    tools_by_id[cid] = call
                    calls.append(call)
            messages.append(
                Message(role="assistant", content="\n".join(t for t in texts if t), tool_calls=calls, ts=ts)
            )
        elif kind == "user" or msg.get("role") == "user":
            # tool_result blocks ride in user messages
            if isinstance(content, list):
                only_tools = True
                user_bits: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        only_tools = False
                        continue
                    if block.get("type") == "tool_result":
                        cid = str(block.get("tool_use_id") or block.get("tool_call_id") or "")
                        result = block.get("content")
                        if not isinstance(result, str):
                            result = json.dumps(result) if result is not None else ""
                        is_err = bool(block.get("is_error"))
                        if cid in tools_by_id:
                            tools_by_id[cid].result = result
                            if is_err:
                                tools_by_id[cid].outcome = "error"
                    else:
                        only_tools = False
                        if block.get("type") == "text":
                            user_bits.append(str(block.get("text") or ""))
                if not only_tools:
                    text = "\n".join(user_bits) if user_bits else _text_from_content(content)
                    if text.strip():
                        messages.append(Message(role="user", content=text, ts=ts))
            else:
                text = _text_from_content(content)
                if text.strip():
                    messages.append(Message(role="user", content=text, ts=ts))

    return Trace(
        source=str(p),
        session_id=session_id,
        messages=messages,
        tools=list(tools_by_id.values()),
    )
