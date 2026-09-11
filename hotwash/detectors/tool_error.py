from __future__ import annotations

import re

from hotwash.model import Finding, ToolCall, Trace

FAILED = {"error", "failed", "failure", "timeout"}
SUCCESS_CLAIM = re.compile(
    r"\b(done|fixed|it'?s live|is live|succeeded|all tests pass|pushed to|deploy succeeded)\b",
    re.I,
)
EXIT_FAIL = re.compile(r"^exit:\s*[1-9]", re.M)


def _failed(tool: ToolCall) -> bool:
    if (tool.outcome or "").lower() in FAILED:
        return True
    if EXIT_FAIL.search(tool.result or ""):
        return True
    return False


def run(trace: Trace) -> list[Finding]:
    failed = [t for t in trace.tools if _failed(t)]
    if not failed:
        return []

    later_ok = {
        t.name.lower()
        for t in trace.tools
        if not _failed(t) and t.name.lower() in {f.name.lower() for f in failed}
    }
    claimed = bool(SUCCESS_CLAIM.search(trace.assistant_text()))
    findings: list[Finding] = []
    seen: set[str] = set()
    for tool in failed:
        key = tool.name.lower()
        if key in seen:
            continue
        seen.add(key)
        if key in later_ok:
            continue
        severity = "error" if claimed else "warn"
        title = (
            f"tool {tool.name} failed, then the assistant claimed success"
            if claimed
            else f"tool {tool.name} failed and was not retried"
        )
        findings.append(
            Finding(
                detector="tool_error",
                severity=severity,
                title=title,
                detail="A tool returned failure. Either retry it to success or do not claim the work is done.",
                evidence=_snip(f"{tool.name} outcome={tool.outcome or '-'}\n{tool.result}"),
            )
        )
        if len(findings) >= 8:
            break
    return findings


def _snip(text: str, n: int = 400) -> str:
    return text[:n]
