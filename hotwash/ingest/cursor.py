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


def _result_text(block: dict[str, Any]) -> str:
    result = block.get("content")
    if result is None:
        result = block.get("result")
    if isinstance(result, str):
        return result
    if result is None:
        return ""
    return json.dumps(result)


def load_cursor(path: str | Path) -> Trace:
    """Cursor agent-transcript JSONL (role + message.content blocks)."""
    p = Path(path)
    tools_by_id: dict[str, ToolCall] = {}
    messages: list[Message] = []
    session_id = sniff_session_id(first_objects(p)) or p.stem
    n_calls = 0

    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        role = str(row.get("role") or msg.get("role") or "")
        content = msg.get("content") if msg else row.get("content")
        ts = str(row.get("timestamp") or row.get("ts") or "")

        if role == "assistant":
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
                    n_calls += 1
                    cid = str(block.get("id") or f"t{n_calls}")
                    args = block.get("input")
                    if args is None:
                        args = block.get("arguments")
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
        elif role == "user":
            if isinstance(content, list):
                only_tools = True
                user_bits: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        only_tools = False
                        continue
                    if block.get("type") == "tool_result":
                        cid = str(block.get("tool_use_id") or block.get("tool_call_id") or block.get("id") or "")
                        result = _result_text(block)
                        is_err = bool(block.get("is_error"))
                        if not cid:
                            for pending in reversed(list(tools_by_id.values())):
                                if not pending.result:
                                    cid = pending.id
                                    break
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
