from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed, is_write_tool
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(format this|run black|run prettier|run ruff format)\b", re.I)
CLAIM = re.compile(
    r"\b(I formatted|ran black|prettier succeeded|formatted the file|ruff format succeeded)\b",
    re.I,
)
FORMAT_CMD = re.compile(
    r"\bruff\s+format\b"
    r"|\bblack\b"
    r"|\bprettier\b"
    r"|\bgofmt\b"
    r"|\bcargo\s+fmt\b"
    r"|\bclang-format\b",
    re.I,
)


def _formatted(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if is_write_tool(tool):
            continue
        if FORMAT_CMD.search(command(tool)) or FORMAT_CMD.search(blob(tool)):
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
    if _formatted(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="format_claim",
                severity="error",
                title="claimed a format with no formatter in the trace",
                detail="The assistant said it formatted. No successful formatter appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="format_claim",
            severity="warn",
            title="a format was requested; no formatter in the trace",
            detail="The user asked to format. The session never ran a formatter, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
