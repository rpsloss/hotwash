from __future__ import annotations

from hotwash.model import Finding, Trace


def run(trace: Trace) -> list[Finding]:
    last = None
    for tool in trace.tools_named("todo_write"):
        last = tool
    if last is None:
        return []
    args = last.args_dict()
    items = args.get("todos") or []
    if not isinstance(items, list):
        return []
    open_items = [
        it
        for it in items
        if isinstance(it, dict) and str(it.get("status") or "") in {"pending", "in_progress"}
    ]
    if not open_items:
        return []
    names = ", ".join(str(it.get("content") or it.get("id") or "?") for it in open_items)
    return [
        Finding(
            detector="todos",
            severity="warn",
            title=f"{len(open_items)} todo(s) still open at session end",
            detail="The last todo_write still has pending or in_progress items.",
            evidence=names,
        )
    ]
