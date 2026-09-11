from __future__ import annotations

import re

from hotwash.detectors.util import failed, is_write_tool
from hotwash.model import Finding, Trace

# Slash path, dotted filename (foo.py), or leading-dot file (.env).
PATH = (
    r"[`'\"]?"
    r"(?:"
    r"[\w./~+-]*/[\w./~+-]+"
    r"|"
    r"\.[A-Za-z][\w.-]*"
    r"|"
    r"[A-Za-z_][\w-]*\.[A-Za-z0-9][\w.-]*"
    r")"
    r"[`'\"]?"
)
CLAIM = re.compile(
    r"(?:"
    r"\bI (?:updated|wrote|created|edited|saved) the file\b"
    r"|\b(?:updated|wrote) " + PATH +
    r"|\bchanges are in " + PATH +
    r")",
    re.I,
)


def _wrote(trace: Trace) -> bool:
    for tool in trace.tools:
        if is_write_tool(tool) and not failed(tool):
            return True
    return False


def run(trace: Trace) -> list[Finding]:
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
    if not claimed:
        return []
    if _wrote(trace):
        return []
    return [
        Finding(
            detector="write_claim",
            severity="error",
            title="claimed a file write with no write tool",
            detail="The assistant said it wrote or updated a file. No successful write tool appears in the tools.",
            evidence=snip.strip() or _snip(trace.assistant_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
