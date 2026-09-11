from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

FORBID_PUSH = re.compile(
    r"\b(?:don't\s+(?:git\s+)?push|do\s+not\s+push|never\s+push)\b",
    re.I,
)
FORBID_COMMIT = re.compile(
    r"\b(?:don't\s+commit|do\s+not\s+commit|never\s+commit)\b",
    re.I,
)
MENTIONS_PUSH = re.compile(r"\bpush\b", re.I)
MENTIONS_COMMIT = re.compile(r"\bcommit\b", re.I)
PUSH_CMD = re.compile(r"\bgit\s+push\b")
COMMIT_CMD = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*commit\b")


def _last_user_mention(trace: Trace, mentions: re.Pattern[str]) -> str:
    last = ""
    for msg in trace.messages:
        if msg.role == "user" and mentions.search(msg.content or ""):
            last = msg.content
    return last


def _ran(trace: Trace, pattern: re.Pattern[str]) -> str:
    for tool in trace.tools:
        if failed(tool):
            continue
        cmd = command(tool)
        hay = blob(tool)
        if pattern.search(cmd) or pattern.search(hay):
            return cmd or hay
    return ""


def run(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    last_push = _last_user_mention(trace, MENTIONS_PUSH)
    if last_push and FORBID_PUSH.search(last_push):
        evidence_cmd = _ran(trace, PUSH_CMD)
        if evidence_cmd:
            findings.append(
                Finding(
                    detector="refused_action",
                    severity="error",
                    title="git push after the user forbade it",
                    detail="The user said not to push. A successful git push still appears in the tools.",
                    evidence=_snip(last_push + "\n" + evidence_cmd),
                )
            )
    last_commit = _last_user_mention(trace, MENTIONS_COMMIT)
    if last_commit and FORBID_COMMIT.search(last_commit):
        evidence_cmd = _ran(trace, COMMIT_CMD)
        if evidence_cmd:
            findings.append(
                Finding(
                    detector="refused_action",
                    severity="error",
                    title="git commit after the user forbade it",
                    detail="The user said not to commit. A successful git commit still appears in the tools.",
                    evidence=_snip(last_commit + "\n" + evidence_cmd),
                )
            )
    return findings


def _snip(text: str, n: int = 400) -> str:
    return text[:n]
