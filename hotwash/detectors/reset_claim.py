from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(git\s+reset|reset hard)\b", re.I)
CLAIM = re.compile(
    r"\b(I reset|hard reset is done|reset to origin/main|undid the commit with reset)\b",
    re.I,
)
RESET_CMD = re.compile(r"\bgit\s+reset\b")


def _reset(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if RESET_CMD.search(command(tool)) or RESET_CMD.search(blob(tool)):
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
    if _reset(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="reset_claim",
                severity="error",
                title="claimed a git reset with no git reset command",
                detail="The assistant said it ran git reset. No successful git reset appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="reset_claim",
            severity="warn",
            title="a git reset was requested; no git reset command in the trace",
            detail="The user asked to git reset. The session never ran git reset, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
