from __future__ import annotations

import re

from hotwash.model import Finding, Trace

SHIP_ASK = re.compile(
    r"\b(vercel|deploy|production|live site|push to git|update the (site|page)|profile pic|about page)\b",
    re.I,
)
SHIP_CLAIM = re.compile(
    r"\b(it'?s live|is live|now live|deploy succeeded|production (is|has)|verified (the )?(live|production)|you can check now|hard-refresh)\b",
    re.I,
)
VERIFY_HINT = re.compile(
    r"\b(curl|httpie|playwright|agent-browser|wget|npm test|pytest|vitest|cypress)\b",
    re.I,
)


def run(trace: Trace) -> list[Finding]:
    asked = bool(SHIP_ASK.search(trace.user_text()))
    if not asked:
        return []

    verify_tools = [t for t in trace.tools if VERIFY_HINT.search(t.blob())]
    findings: list[Finding] = []

    claimed = False
    claim_snip = ""
    for msg in trace.messages:
        if msg.role != "assistant":
            continue
        m = SHIP_CLAIM.search(msg.content)
        if m:
            claimed = True
            claim_snip = msg.content[max(0, m.start() - 40) : m.end() + 80]
            break

    if claimed and not verify_tools:
        findings.append(
            Finding(
                detector="ship_claim",
                severity="error",
                title="claimed a live ship without a verify tool",
                detail="User asked to deploy. Assistant said it was live. Trace has no curl, browser, or test against the result.",
                evidence=claim_snip.strip(),
            )
        )
    elif asked and not verify_tools:
        findings.append(
            Finding(
                detector="ship_claim",
                severity="warn",
                title="ship was requested; no verify tool in the trace",
                detail="A deploy or site change was asked for. The session never curled, browsed, or tested the result.",
                evidence="user asked: " + _first_user(trace)[:240],
            )
        )
    return findings


def _first_user(trace: Trace) -> str:
    for m in trace.messages:
        if m.role == "user":
            return m.content
    return ""
