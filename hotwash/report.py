from __future__ import annotations

from hotwash.model import Finding, Trace

RANKS = (
    (0, "CLEAN", "Nothing in the trace tripped a detector."),
    (1, "NOTES", "Warnings only. The work may still be good."),
    (2, "FINDINGS", "At least one error. The claim and the trace disagree."),
)


def rank(findings: list[Finding]) -> tuple[str, str]:
    if any(f.severity == "error" for f in findings):
        return RANKS[2][1], RANKS[2][2]
    if findings:
        return RANKS[1][1], RANKS[1][2]
    return RANKS[0][1], RANKS[0][2]


def render_text(trace: Trace, findings: list[Finding]) -> str:
    label, blurb = rank(findings)
    users = sum(1 for m in trace.messages if m.role == "user")
    assistants = sum(1 for m in trace.messages if m.role == "assistant")
    lines = [
        "HOTWASH",
        "after-action review",
        "",
        f"source     {trace.source}",
        f"session    {trace.session_id or '-'}",
        f"turns      {users} user / {assistants} assistant",
        f"tools      {len(trace.tools)}",
        f"findings   {len(findings)}",
        f"rank       {label}",
        f"           {blurb}",
        "",
    ]
    if not findings:
        lines.append("No findings. The trace does not contradict the claims we can check.")
        return "\n".join(lines) + "\n"
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. {f.line()}")
        lines.append(f"   {f.detail}")
        if f.evidence:
            ev = f.evidence.replace("\n", "\n   ")
            lines.append(f"   evidence: {ev}")
        lines.append("")
    return "\n".join(lines)


def render_md(trace: Trace, findings: list[Finding]) -> str:
    label, blurb = rank(findings)
    users = sum(1 for m in trace.messages if m.role == "user")
    assistants = sum(1 for m in trace.messages if m.role == "assistant")
    parts = [
        "# Hotwash",
        "",
        f"**Rank:** {label}. {blurb}",
        "",
        f"- Source: `{trace.source}`",
        f"- Session: `{trace.session_id or '-'}`",
        f"- Turns: {users} user / {assistants} assistant",
        f"- Tools: {len(trace.tools)}",
        f"- Findings: {len(findings)}",
        "",
    ]
    if not findings:
        parts.append("No findings.")
        parts.append("")
        return "\n".join(parts)
    parts.append("## Findings")
    parts.append("")
    for f in findings:
        parts.append(f"### {f.title}")
        parts.append("")
        parts.append(f"- Detector: `{f.detector}`")
        parts.append(f"- Severity: `{f.severity}`")
        parts.append(f"- {f.detail}")
        if f.evidence:
            parts.append("")
            parts.append("```")
            parts.append(f.evidence[:2000])
            parts.append("```")
        parts.append("")
    return "\n".join(parts)


def to_json(trace: Trace, findings: list[Finding]) -> dict:
    label, blurb = rank(findings)
    return {
        "source": trace.source,
        "session_id": trace.session_id,
        "rank": label,
        "blurb": blurb,
        "tools": len(trace.tools),
        "messages": len(trace.messages),
        "findings": [
            {
                "detector": f.detector,
                "severity": f.severity,
                "title": f.title,
                "detail": f.detail,
                "evidence": f.evidence,
            }
            for f in findings
        ],
    }
