from __future__ import annotations

import re

from hotwash.detectors.tool_error import _failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(push to git|git push|commit and push|push (it|this) to (github|origin|main))\b", re.I)
CLAIM = re.compile(r"\b(pushed to (main|origin|github)|git push succeeded|it's on github)\b", re.I)
PUSH_CMD = re.compile(r"\bgit\s+push\b")


def _pushed(trace: Trace) -> bool:
    for tool in trace.tools:
        if _failed(tool):
            continue
        if PUSH_CMD.search(tool.blob()):
            return True
    return False


def run(trace: Trace) -> list[Finding]:
    asked = bool(ASK.search(trace.user_text()))
    claimed = False
    snip = ""
    for msg in trace.messages:
        if msg.role != "assistant":
            continue
        m = CLAIM.search(msg.content)
        if m:
            claimed = True
            snip = msg.content[max(0, m.start() - 40) : m.end() + 80]
            break
    if not asked and not claimed:
        return []
    if _pushed(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="push_claim",
                severity="error",
                title="claimed a git push that is not in the trace",
                detail="The assistant said the commit was pushed. No successful git push appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="push_claim",
            severity="warn",
            title="a push was requested; no git push in the trace",
            detail="The user asked to push. The session never ran git push, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
