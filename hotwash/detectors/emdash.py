from __future__ import annotations

from hotwash.model import Finding, Trace

EM = "\u2014"  # em dash
EN = "\u2013"  # en dash used as a pause

WRITE_TOOLS = {
    "search_replace",
    "write",
    "edit",
    "str_replace",
    "create_file",
}


def _written_text(tool) -> str:
    """Only the text the agent is inserting, not old_string being deleted."""
    args = tool.args_dict()
    name = tool.name.lower()
    if name == "search_replace":
        return str(args.get("new_string") or args.get("new_content") or "")
    if name in {"write", "create_file", "edit", "str_replace"}:
        return str(args.get("content") or args.get("new_string") or args.get("new_content") or "")
    return tool.arguments


def run(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    for tool in trace.tools:
        if tool.name.lower() not in WRITE_TOOLS:
            continue
        blob = _written_text(tool)
        if EM not in blob and EN not in blob:
            continue
        args = tool.args_dict()
        path = str(args.get("path") or args.get("file_path") or args.get("target_file") or "")
        kind = "em-dash" if EM in blob else "en-dash"
        findings.append(
            Finding(
                detector="emdash",
                severity="error",
                title=f"{kind} written into {path or tool.name}",
                detail="User-facing copy with em/en dashes is a common agent tell. Use a period, comma, or colon.",
                evidence=(path or tool.name) + "\n" + _snip(blob),
            )
        )
    # assistant prose is a weaker tell
    for i, msg in enumerate(trace.messages):
        if msg.role != "assistant" or EM not in msg.content:
            continue
        findings.append(
            Finding(
                detector="emdash",
                severity="warn",
                title=f"em-dash in assistant message #{i + 1}",
                detail="Spoken copy on the site was the original complaint. Prose in the session still leaks the same mark.",
                evidence=_snip(msg.content),
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
