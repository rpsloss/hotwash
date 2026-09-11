from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(please merge|merge this PR|git merge)\b", re.I)
CLAIM = re.compile(
    r"\b(I merged|merge is done|merged into main|PR is merged)\b",
    re.I,
)
MERGE_CMD = re.compile(
    r"\bgit\s+merge\b"
    r"|\bgh\s+pr\s+merge\b"
    r"|\bhub\s+merge\b"
)


def _merged(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if MERGE_CMD.search(command(tool)) or MERGE_CMD.search(blob(tool)):
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
    if _merged(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="merge_claim",
                severity="error",
                title="claimed a merge with no git merge / gh pr merge",
                detail="The assistant said it merged a branch or PR. No successful git merge, gh pr merge, or hub merge appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="merge_claim",
            severity="warn",
            title="a merge was requested; no merge command in the trace",
            detail="The user asked to merge. The session never ran git merge, gh pr merge, or hub merge, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
