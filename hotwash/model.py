from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""
    result: str = ""
    outcome: str = ""
    ts: str = ""

    def args_dict(self) -> dict[str, Any]:
        import json

        raw = self.arguments.strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": self.arguments}
        return data if isinstance(data, dict) else {"_value": data}

    def blob(self) -> str:
        return "\n".join([self.name, self.arguments, self.result])


@dataclass
class Message:
    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    ts: str = ""


@dataclass
class Finding:
    detector: str
    severity: str  # error | warn | info
    title: str
    detail: str
    evidence: str = ""

    def line(self) -> str:
        return f"[{self.severity.upper():5}] {self.detector}: {self.title}"


@dataclass
class Trace:
    source: str
    session_id: Optional[str] = None
    messages: list[Message] = field(default_factory=list)
    tools: list[ToolCall] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def user_text(self) -> str:
        return "\n".join(m.content for m in self.messages if m.role == "user")

    def assistant_text(self) -> str:
        return "\n".join(m.content for m in self.messages if m.role == "assistant")

    def tools_named(self, *names: str) -> list[ToolCall]:
        want = {n.lower() for n in names}
        return [t for t in self.tools if t.name.lower() in want]

    def to_dict(self, result_limit: int = 400) -> dict[str, Any]:
        def clip(text: str) -> str:
            if len(text) <= result_limit:
                return text
            return text[:result_limit] + "..."

        return {
            "source": self.source,
            "session_id": self.session_id,
            "messages": [
                {
                    "role": m.role,
                    "content": clip(m.content),
                    "tool_calls": [c.id for c in m.tool_calls],
                    "ts": m.ts,
                }
                for m in self.messages
            ],
            "tools": [
                {
                    "id": t.id,
                    "name": t.name,
                    "arguments": clip(t.arguments),
                    "result": clip(t.result),
                    "outcome": t.outcome,
                    "ts": t.ts,
                }
                for t in self.tools
            ],
        }
