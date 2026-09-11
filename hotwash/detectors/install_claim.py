from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

ASK = re.compile(r"\b(pip install|npm install|please install)\b", re.I)
CLAIM = re.compile(
    r"\b(I installed|pip install succeeded|npm install is done|package is installed)\b",
    re.I,
)
INSTALL_CMD = re.compile(
    r"\bpip(3)?\s+install\b"
    r"|\bnpm\s+install\b"
    r"|\bpnpm\s+(install|add)\b"
    r"|\byarn\s+add\b"
    r"|\bpoetry\s+add\b"
    r"|\bgo\s+get\b"
    r"|\bcargo\s+add\b",
    re.I,
)


def _installed(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if INSTALL_CMD.search(command(tool)) or INSTALL_CMD.search(blob(tool)):
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
    if _installed(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="install_claim",
                severity="error",
                title="claimed a package install with no install command",
                detail="The assistant said it installed a package. No successful pip install / npm install / equivalent appears in the tools.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="install_claim",
            severity="warn",
            title="a package install was requested; no install command in the trace",
            detail="The user asked to install a package. The session never ran an install command, or it failed.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
