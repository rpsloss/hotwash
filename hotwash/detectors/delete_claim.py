from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
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
    r"\bI deleted\b"
    r"|\bI removed the file\b"
    r"|\b(?:deleted|removed) " + PATH +
    r")",
    re.I,
)
DELETE_TOOLS = {"delete_file", "delete", "remove_file", "unlink"}
DELETE_CMD = re.compile(r"\brm\s+|\bdel\s+|\bunlink\s+|\bgit\s+rm\b")


def _deleted(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if tool.name.lower() == "search_replace":
            continue
        if tool.name.lower() in DELETE_TOOLS:
            return True
        if DELETE_CMD.search(command(tool)) or DELETE_CMD.search(blob(tool)):
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
    if _deleted(trace):
        return []
    return [
        Finding(
            detector="delete_claim",
            severity="error",
            title="claimed a file delete with no delete tool",
            detail="The assistant said it deleted or removed a file. No successful delete tool appears in the tools.",
            evidence=snip.strip() or _snip(trace.assistant_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
