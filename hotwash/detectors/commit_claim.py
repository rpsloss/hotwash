from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(
    r"\b(git commit|commit (the )?(changes|this|it|fix)|commit and push|make a commit|please commit)\b",
    re.I,
)
CLAIM = re.compile(
    r"\b((?:I|we) committed|committed (the )?(changes|fix|it)|git commit succeeded|created a commit|commit (is|was) (in|done))\b",
    re.I,
)
COMMIT_CMD = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*commit\b")


def _committed(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if COMMIT_CMD.search(command(tool)) or COMMIT_CMD.search(blob(tool)):
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
    if _committed(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="commit_claim",
                severity="error",
                title="claimed a git commit that is not in the trace",
                detail="The assistant said it committed. No successful git commit appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="commit_claim",
            severity="warn",
            title="a commit was requested; no git commit in the trace",
            detail="The user asked to commit. The session never ran git commit, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
