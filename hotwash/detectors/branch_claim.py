from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(create a branch|git checkout -b)\b", re.I)
CLAIM = re.compile(
    r"\b(I created a branch|checked out a new branch|branch is ready|switched to branch)\b",
    re.I,
)
BRANCH_CMD = re.compile(
    r"\bgit\s+checkout\s+-b\b"
    r"|\bgit\s+switch\s+-c\b"
    r"|\bgit\s+branch\s+[^-]"
)


def _branched(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if BRANCH_CMD.search(command(tool)) or BRANCH_CMD.search(blob(tool)):
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
    if _branched(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="branch_claim",
                severity="error",
                title="claimed a git branch with no branch command",
                detail="The assistant said it created or switched to a branch. No successful git checkout -b, git switch -c, or git branch <name> appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="branch_claim",
            severity="warn",
            title="a branch was requested; no branch command in the trace",
            detail="The user asked to create a branch. The session never ran git checkout -b, git switch -c, or git branch <name>, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
