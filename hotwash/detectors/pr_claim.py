from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(
    r"\b(open (a |the )?(pr|pull request)|create (a |the )?(pr|pull request)|"
    r"gh pr create|submit (a |the )?(pr|pull request)|make a (pr|pull request))\b",
    re.I,
)
CLAIM = re.compile(
    r"\b(opened (a |the )?(pr|pull request)|created (a |the )?(pr|pull request)|"
    r"PR is (up|ready|open)|pull request is (up|ready|open)|it's in (a |the )?pr)\b",
    re.I,
)
PR_CMD = re.compile(r"\b(gh\s+pr\s+create|hub\s+pull-request|glab\s+mr\s+create)\b")


def _opened_pr(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        hay = command(tool) + "\n" + blob(tool)
        if PR_CMD.search(hay):
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
    if _opened_pr(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="pr_claim",
                severity="error",
                title="claimed a pull request that is not in the trace",
                detail="The assistant said a PR was opened. No successful gh pr create (or hub/glab equivalent) appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="pr_claim",
            severity="warn",
            title="a pull request was requested; none in the trace",
            detail="The user asked to open a PR. The session never ran gh pr create, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
