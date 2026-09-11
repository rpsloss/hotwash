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
    r"\bI read the file\b"
    r"|\bI (?:read|opened|inspected|looked at) " + PATH +
    r")",
    re.I,
)
READ_NAMES = {"read_file", "read", "readfile"}
READ_CMD = re.compile(r"\b(?:cat|type)\s+\S", re.I)


def _read(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if tool.name.lower() in READ_NAMES:
            return True
        if READ_CMD.search(command(tool)) or READ_CMD.search(blob(tool)):
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
    if _read(trace):
        return []
    return [
        Finding(
            detector="read_claim",
            severity="error",
            title="claimed a file read with no read tool",
            detail="The assistant said it read or opened a file. No successful read tool appears in the tools.",
            evidence=snip.strip() or _snip(trace.assistant_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
