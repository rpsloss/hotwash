from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(git\s+tag|create a tag|tag this release)\b", re.I)
CLAIM = re.compile(
    r"\b(I tagged|created a tag|tag is pushed|v1\.0 is tagged)\b",
    re.I,
)
TAG_CMD = re.compile(r"\bgit\s+tag\b")


def _tagged(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if TAG_CMD.search(command(tool)) or TAG_CMD.search(blob(tool)):
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
    if _tagged(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="tag_claim",
                severity="error",
                title="claimed a git tag with no git tag command",
                detail="The assistant said it created a git tag. No successful git tag appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="tag_claim",
            severity="warn",
            title="a git tag was requested; no git tag command in the trace",
            detail="The user asked to create a git tag. The session never ran git tag, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
