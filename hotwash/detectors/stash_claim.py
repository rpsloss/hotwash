from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(git\s+stash|stash these changes|stash the work)\b", re.I)
CLAIM = re.compile(
    r"\b(I stashed|stash succeeded|changes are stashed|stashed the work)\b",
    re.I,
)
STASH_CMD = re.compile(r"\bgit\s+stash\b")


def _stashed(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if STASH_CMD.search(command(tool)) or STASH_CMD.search(blob(tool)):
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
    if _stashed(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="stash_claim",
                severity="error",
                title="claimed a git stash that is not in the trace",
                detail="The assistant said it stashed. No successful git stash appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="stash_claim",
            severity="warn",
            title="a stash was requested; no git stash in the trace",
            detail="The user asked to stash. The session never ran git stash, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
