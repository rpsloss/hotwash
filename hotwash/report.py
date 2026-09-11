from __future__ import annotations

import html as html_lib

from hotwash.model import Finding, Trace
from hotwash.redact import redact


def _esc(text: str) -> str:
    return html_lib.escape(str(text), quote=True)

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
            ev = redact(f.evidence).replace("\n", "\n   ")
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
            parts.append(redact(f.evidence)[:2000])
            parts.append("```")
        parts.append("")
    return "\n".join(parts)


_HTML_CSS = """
:root { color-scheme: dark; }
html, body { margin: 0; padding: 0; }
body {
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
  background: #121418;
  color: #e8eaed;
  line-height: 1.45;
  padding: 24px 20px 48px;
}
main { max-width: 880px; margin: 0 auto; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  color: #9aa0a6;
  margin: 0 0 4px;
}
h1 { font-size: 1.8rem; margin: 0 0 12px; }
h2 { font-size: 1.15rem; margin: 28px 0 12px; }
h3 { font-size: 1.05rem; margin: 0 0 8px; }
.rank {
  font-size: 1.05rem;
  padding: 10px 12px;
  border-radius: 6px;
  background: #1c1f26;
  border-left: 4px solid #9aa0a6;
}
.rank-CLEAN { border-left-color: #8bd17c; }
.rank-NOTES { border-left-color: #ffd166; }
.rank-FINDINGS { border-left-color: #ff6b6b; }
.meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px 16px;
  margin: 18px 0 0;
}
.meta div { background: #1c1f26; padding: 10px 12px; border-radius: 6px; }
.meta dt {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #9aa0a6;
}
.meta dd { margin: 2px 0 0; word-break: break-word; }
table {
  width: 100%;
  border-collapse: collapse;
  background: #1c1f26;
  border-radius: 6px;
  overflow: hidden;
}
th, td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid #2a2f38;
  vertical-align: top;
}
th {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #9aa0a6;
}
tr:last-child td { border-bottom: 0; }
.finding {
  background: #1c1f26;
  border-radius: 6px;
  padding: 14px 16px;
  margin: 12px 0;
  border-left: 4px solid #9aa0a6;
}
.finding.sev-error { border-left-color: #ff6b6b; }
.finding.sev-warn { border-left-color: #ffd166; }
.finding.sev-info { border-left-color: #7ec8e3; }
.pill {
  display: inline-block;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #2a2f38;
  color: #e8eaed;
  margin-right: 6px;
}
.pill-error { background: #4a1f22; color: #ffb4b4; }
.pill-warn { background: #3d3214; color: #ffe08a; }
.pill-info { background: #1a3340; color: #b7e3f3; }
.detail { margin: 8px 0; }
pre {
  background: #0d0f12;
  color: #d7dbe0;
  padding: 10px 12px;
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.85rem;
}
.empty { color: #9aa0a6; }
@media print {
  :root { color-scheme: light; }
  body { background: #fff; color: #111; padding: 0; }
  .rank, .meta div, table, .finding, pre { background: #fff; color: #111; }
  .rank, .finding { border: 1px solid #ccc; border-left-width: 4px; }
  th, td { border-bottom: 1px solid #ddd; }
  .pill { border: 1px solid #ccc; background: #fff; color: #111; }
  pre { border: 1px solid #ddd; }
}
"""


def render_html(trace: Trace, findings: list[Finding]) -> str:
    label, blurb = rank(findings)
    users = sum(1 for m in trace.messages if m.role == "user")
    assistants = sum(1 for m in trace.messages if m.role == "assistant")
    session = trace.session_id or "-"
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Hotwash {_esc(label)}</title>",
        f"<style>{_HTML_CSS.strip()}</style>",
        "</head>",
        "<body>",
        "<main>",
        '<p class="eyebrow">after-action review</p>',
        "<h1>Hotwash</h1>",
        f'<p class="rank rank-{_esc(label)}">Rank: {_esc(label)}. {_esc(blurb)}</p>',
        '<dl class="meta">',
        f"<div><dt>Source</dt><dd>{_esc(trace.source)}</dd></div>",
        f"<div><dt>Session</dt><dd>{_esc(session)}</dd></div>",
        f"<div><dt>Turns</dt><dd>{users} user / {assistants} assistant</dd></div>",
        f"<div><dt>Tools</dt><dd>{len(trace.tools)}</dd></div>",
        f"<div><dt>Findings</dt><dd>{len(findings)}</dd></div>",
        "</dl>",
    ]
    if not findings:
        parts.append('<p class="empty">No findings. The trace does not contradict the claims we can check.</p>')
    else:
        parts.append("<h2>Findings</h2>")
        parts.append("<table>")
        parts.append("<thead><tr><th>#</th><th>Severity</th><th>Detector</th><th>Title</th></tr></thead>")
        parts.append("<tbody>")
        for i, f in enumerate(findings, 1):
            parts.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{_esc(f.severity)}</td>"
                f"<td>{_esc(f.detector)}</td>"
                f"<td>{_esc(f.title)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
        for i, f in enumerate(findings, 1):
            sev = _esc(f.severity)
            parts.append(f'<article class="finding sev-{sev}">')
            parts.append(f"<h3>{i}. {_esc(f.title)}</h3>")
            parts.append(
                f'<p><span class="pill pill-{sev}">{sev}</span>'
                f'<span class="pill">{_esc(f.detector)}</span></p>'
            )
            parts.append(f'<p class="detail">{_esc(f.detail)}</p>')
            if f.evidence:
                parts.append(f"<pre>{_esc(redact(f.evidence)[:2000])}</pre>")
            parts.append("</article>")
    parts.extend(["</main>", "</body>", "</html>", ""])
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
                "evidence": redact(f.evidence),
            }
            for f in findings
        ],
    }
