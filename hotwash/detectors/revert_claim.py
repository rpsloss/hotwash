from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(
    r"\b(revert that commit|git revert|undo that commit with revert)\b",
    re.I,
)
CLAIM = re.compile(
    r"\b(I reverted|revert succeeded|reverted the commit)\b",
    re.I,
)
REVERT_CMD = re.compile(r"\bgit\s+revert\b")


def _reverted(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if REVERT_CMD.search(command(tool)) or REVERT_CMD.search(blob(tool)):
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
    if _reverted(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="revert_claim",
                severity="error",
                title="claimed a git revert that is not in the trace",
                detail="The assistant said it reverted. No successful git revert appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="revert_claim",
            severity="warn",
            title="a revert was requested; no git revert in the trace",
            detail="The user asked to revert. The session never ran git revert, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
