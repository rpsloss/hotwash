from __future__ import annotations

from hotwash.detectors.util import is_write_tool, write_path, written_text
from hotwash.model import Finding, Trace

EM = "\u2014"  # em dash
EN = "\u2013"  # en dash used as a pause


def run(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    for tool in trace.tools:
        if not is_write_tool(tool):
            continue
        blob = written_text(tool)
        if EM not in blob and EN not in blob:
            continue
        path = write_path(tool)
        kind = "em-dash" if EM in blob else "en-dash"
        findings.append(
            Finding(
                detector="emdash",
                severity="error",
                title=f"{kind} written into {path or tool.name}",
                detail="Em/en dashes in written files are a common generated-text tell. Prefer a period, comma, or colon.",
                evidence=(path or tool.name) + "\n" + _snip(blob),
            )
        )
    return findings


def _snip(text: str, n: int = 240) -> str:
    text = " ".join(text.split())
    if EM in text:
        i = text.index(EM)
        start = max(0, i - 80)
        return text[start : start + n]
    return text[:n]
