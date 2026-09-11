from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(rebase onto main|git rebase|rebase this branch)\b", re.I)
CLAIM = re.compile(
    r"\b(I rebased|rebase succeeded|rebased onto main)\b",
    re.I,
)
REBASE_CMD = re.compile(r"\bgit\s+rebase\b")


def _rebased(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if REBASE_CMD.search(command(tool)) or REBASE_CMD.search(blob(tool)):
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
    if _rebased(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="rebase_claim",
                severity="error",
                title="claimed a git rebase that is not in the trace",
                detail="The assistant said it rebased. No successful git rebase appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="rebase_claim",
            severity="warn",
            title="a rebase was requested; no git rebase in the trace",
            detail="The user asked to rebase. The session never ran git rebase, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
