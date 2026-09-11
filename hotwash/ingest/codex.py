from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hotwash.detectors.util import EXIT_FAIL
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
                if item.get("type") in {"output_text", "text", "input_text"}:
                    parts.append(str(item.get("text") or ""))
                elif "text" in item:
                    parts.append(str(item["text"]))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        return str(content.get("text") or content.get("message") or "")
    return str(content)


def _args_to_str(args: Any) -> str:
    if args is None:
        return ""
    if isinstance(args, str):
        return args
    return json.dumps(args)


def _result_and_outcome(output: Any) -> tuple[str, str]:
    if output is None:
        return "", ""
    if isinstance(output, dict):
        text = output.get("output") or output.get("content") or output.get("text")
        if not isinstance(text, str):
            text = json.dumps(output) if text is None else str(text)
        exit_code = output.get("exit_code")
        if exit_code is None:
            exit_code = output.get("exitcode")
        if exit_code is None and output.get("metadata"):
            meta = output["metadata"]
            if isinstance(meta, dict):
                exit_code = meta.get("exit_code") or meta.get("exitcode")
        if exit_code is None:
            outcome = "error" if EXIT_FAIL.search(text) else ""
        else:
            try:
                outcome = "error" if int(exit_code) != 0 else "success"
            except (TypeError, ValueError):
                outcome = "error" if str(exit_code) not in {"0", ""} else "success"
        return text, outcome
    text = str(output)
    outcome = "error" if EXIT_FAIL.search(text) else ""
    return text, outcome


def load_codex(path: str | Path) -> Trace:
    """OpenAI Codex CLI rollout JSONL (~/.codex/sessions/**/rollout-*.jsonl)."""
    p = Path(path)
    tools_by_id: dict[str, ToolCall] = {}
    messages: list[Message] = []
    session_id = p.stem
    pending: list[ToolCall] = []

    def flush_pending(ts: str = "") -> None:
        nonlocal pending
        if not pending:
            return
        messages.append(Message(role="assistant", content="", tool_calls=list(pending), ts=ts))
        pending = []

    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = str(row.get("type") or row.get("record_type") or "")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        ts = str(row.get("timestamp") or payload.get("timestamp") or "")

        if kind == "session_meta":
            sid = payload.get("id") or payload.get("session_id")
            if sid:
                session_id = str(sid)
            continue

        inner = str(payload.get("type") or "")

        if kind == "event_msg" and inner == "user_message":
            flush_pending(ts)
            text = str(payload.get("message") or payload.get("text") or "")
            if text.strip():
                messages.append(Message(role="user", content=text, ts=ts))
            continue

        if kind == "event_msg" and inner == "agent_message":
            flush_pending(ts)
            text = str(payload.get("message") or payload.get("text") or "")
            if text.strip():
                messages.append(Message(role="assistant", content=text, ts=ts))
            continue

        if kind != "response_item":
            continue

        if inner in {"function_call", "custom_tool_call"}:
            cid = str(payload.get("call_id") or payload.get("id") or f"c{len(tools_by_id)}")
            args = payload.get("arguments")
            if args is None:
                args = payload.get("input")
            call = ToolCall(
                id=cid,
                name=str(payload.get("name") or "unknown"),
                arguments=_args_to_str(args),
                ts=ts,
            )
            tools_by_id[cid] = call
            pending.append(call)
            continue

        if inner in {"function_call_output", "custom_tool_call_output"}:
            cid = str(payload.get("call_id") or payload.get("id") or "")
            text, outcome = _result_and_outcome(payload.get("output"))
            if cid in tools_by_id:
                tools_by_id[cid].result = text
                if outcome:
                    tools_by_id[cid].outcome = outcome
            continue

        if inner == "message":
            role = str(payload.get("role") or "assistant")
            text = _flatten_content(payload.get("content"))
            if role == "user":
                flush_pending(ts)
                if text.strip():
                    messages.append(Message(role="user", content=text, ts=ts))
            elif role == "assistant":
                calls = list(pending)
                pending = []
                messages.append(Message(role="assistant", content=text, tool_calls=calls, ts=ts))

    flush_pending()
    return Trace(
        source=str(p),
        session_id=session_id,
        messages=messages,
        tools=list(tools_by_id.values()),
    )
