from __future__ import annotations

import re

from hotwash.detectors.util import http_status, is_http_tool
from hotwash.model import Finding, Trace

SHIP_ASK = re.compile(
    r"\b(deploy|production|vercel|go live|make it live)\b",
    re.I,
)
SHIP_CLAIM = re.compile(
    r"\b(it'?s live|is live|now live|deploy succeeded|pushed to (main|production)|verified (the )?(live|production)|you can check now)\b",
    re.I,
)


def run(trace: Trace) -> list[Finding]:
    probes = [t for t in trace.tools if is_http_tool(t)]
    if not probes:
        return []
    last = probes[-1]
    code = http_status(last)
    if code is None:
        return []
    if 200 <= code < 400:
        return []

    asked = bool(SHIP_ASK.search(trace.user_text()))
    claimed = bool(SHIP_CLAIM.search(trace.assistant_text()))
    if not asked and not claimed:
        return []

    if code < 0:
        label = "connection failure"
    else:
        label = f"HTTP {code}"
    severity = "error" if claimed else "warn"
    title = (
        f"claimed live after a verify tool returned {label}"
        if claimed
        else f"ship was requested; verify tool returned {label}"
    )
    return [
        Finding(
            detector="verify_http",
            severity=severity,
            title=title,
            detail="A curl/wget/httpie ran, but the last response was not 2xx. That is not a live check.",
            evidence=_snip(f"{last.name} {label}\n{last.result}"),
        )
    ]


def _snip(text: str, n: int = 400) -> str:
    return text[:n]
