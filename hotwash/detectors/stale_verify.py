from __future__ import annotations

import re

from hotwash.detectors.util import command, http_status, is_http_tool, is_ship_mutate
from hotwash.model import Finding, Trace

SHIP_ASK = re.compile(
    r"\b(deploy|production|vercel|go live|make it live)\b",
    re.I,
)
SHIP_CLAIM = re.compile(
    r"\b(it'?s live|is live|now live|deploy succeeded|pushed to (main|production)|verified (the )?(live|production)|you can check now)\b",
    re.I,
)


def _is_2xx_probe(tool) -> bool:
    if not is_http_tool(tool):
        return False
    code = http_status(tool)
    return code is not None and 200 <= code < 300


def run(trace: Trace) -> list[Finding]:
    asked = bool(SHIP_ASK.search(trace.user_text()))
    claimed = bool(SHIP_CLAIM.search(trace.assistant_text()))
    if not asked and not claimed:
        return []

    last_http = -1
    last_mut = -1
    http_tool = None
    mut_tool = None
    for i, tool in enumerate(trace.tools):
        if _is_2xx_probe(tool):
            last_http = i
            http_tool = tool
        if is_ship_mutate(tool):
            last_mut = i
            mut_tool = tool
    if last_http < 0 or last_mut < 0:
        return []
    if last_http >= last_mut:
        return []

    severity = "error" if claimed else "warn"
    title = (
        "claimed live after changing the tree; last verify was earlier"
        if claimed
        else "ship was requested; last verify ran before the last change"
    )
    cmd = command(mut_tool) if mut_tool else ""
    ev = f"verify: {http_tool.name if http_tool else '-'}\nthen: {mut_tool.name if mut_tool else '-'} {cmd}".strip()
    return [
        Finding(
            detector="stale_verify",
            severity=severity,
            title=title,
            detail="A curl/wget ran, then the agent wrote or pushed. That check is of the old tree, not the result.",
            evidence=_snip(ev),
        )
    ]


def _snip(text: str, n: int = 400) -> str:
    return text[:n]
