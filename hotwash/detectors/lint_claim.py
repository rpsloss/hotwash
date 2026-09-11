from __future__ import annotations

import re

from hotwash.detectors.util import blob, command, failed
from hotwash.model import Finding, Trace

CLAIM = re.compile(
    r"\b("
    r"lint is clean"
    r"|linter passed"
    r"|no lint errors"
    r"|ruff is clean"
    r"|eslint passed"
    r")\b",
    re.I,
)
ASK = re.compile(r"\b(run lint|run ruff|run eslint)\b", re.I)
LINT_CMD = re.compile(
    r"\bruff\b"
    r"|\beslint\b"
    r"|\bpylint\b"
    r"|\bflake8\b"
    r"|\bnpm\s+run\s+lint\b"
    r"|\bgolangci-lint\b",
    re.I,
)


def _linted(trace: Trace) -> bool:
    for tool in trace.tools:
        if failed(tool):
            continue
        if LINT_CMD.search(command(tool)) or LINT_CMD.search(blob(tool)):
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
    if _linted(trace):
        return []
    if claimed:
        return [
            Finding(
                detector="lint_claim",
                severity="error",
                title="claimed lint is clean with no linter in the trace",
                detail="The assistant said lint is clean. The trace has no successful ruff / eslint / equivalent.",
                evidence=snip.strip() or _snip(trace.assistant_text()),
            )
        ]
    return [
        Finding(
            detector="lint_claim",
            severity="warn",
            title="lint was requested; no linter in the trace",
            detail="The user asked to run lint. No linter command succeeded.",
            evidence=_snip(trace.user_text()),
        )
    ]


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
