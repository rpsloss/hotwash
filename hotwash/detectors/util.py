from __future__ import annotations

import re
from typing import Optional

from hotwash.model import ToolCall

SHELL_TOOLS = {
    "run_terminal_command",
    "bash",
    "shell",
    "shell_command",
    "exec_command",
    "local_shell",
}

WRITE_TOOLS = {
    "search_replace",
    "write",
    "edit",
    "str_replace",
    "create_file",
    "apply_patch",
    "notebookedit",
}

FAILED_OUTCOMES = {"error", "failed", "failure", "timeout"}
EXIT_FAIL = re.compile(
    r"(?im)^(?:exit(?:\s+code)?|command exited with(?:\s+code)?):?\s*([1-9]\d*)"
)
HTTP_STATUS = re.compile(r"(?im)^HTTP/\d(?:\.\d)?\s+(\d{3})\b")
HTTP_TOOL = re.compile(r"\b(curl|httpie|wget)\b", re.I)
SHIP_MUTATE = re.compile(
    r"\bgit\s+(?:-c\s+\S+\s+)*commit\b"
    r"|\bgit\s+push\b"
    r"|\bvercel\b"
    r"|\bnetlify\s+deploy\b"
    r"|\bflyctl\s+deploy\b"
    r"|\bwrangler\s+deploy\b"
    r"|\bkubectl\s+apply\b"
    r"|\bnpm\s+run\s+deploy\b"
    r"|\bdocker\s+push\b"
    r"|\bgh\s+workflow\s+run\b",
    re.I,
)
HTTP_CONNECT_FAIL = re.compile(
    r"curl: \(\d+\)|Could not resolve host|Connection refused|Failed to connect|Couldn'?t connect",
    re.I,
)
BEGIN_PATCH = "*** Begin Patch"


def command(tool: ToolCall) -> str:
    """Normalized command string across Grok, Claude, and Codex tool shapes."""
    args = tool.args_dict()
    raw = args.get("command") or args.get("cmd") or args.get("cmd_string")
    if isinstance(raw, list):
        return " ".join(str(x) for x in raw)
    if raw:
        return str(raw)
    if args.get("_raw"):
        return str(args["_raw"])
    if args.get("_value") is not None:
        val = args["_value"]
        if isinstance(val, list):
            return " ".join(str(x) for x in val)
        return str(val)
    return tool.arguments


def blob(tool: ToolCall) -> str:
    return "\n".join([tool.name, command(tool), tool.arguments, tool.result])


def failed(tool: ToolCall) -> bool:
    if (tool.outcome or "").lower() in FAILED_OUTCOMES:
        return True
    if EXIT_FAIL.search(tool.result or ""):
        return True
    return False


def _plus_lines(patch: str) -> str:
    out: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)


def written_text(tool: ToolCall) -> str:
    """Text the agent is inserting, not old_string / deleted patch lines."""
    args = tool.args_dict()
    name = tool.name.lower()
    if name == "search_replace":
        return str(args.get("new_string") or args.get("new_content") or "")
    if name in {"write", "create_file", "edit", "str_replace", "notebookedit"}:
        return str(args.get("content") or args.get("new_string") or args.get("new_content") or "")
    if name in {"apply_patch", "applypatch"}:
        patch = str(
            args.get("input")
            or args.get("patch")
            or args.get("diff")
            or args.get("command")
            or args.get("_raw")
            or args.get("_value")
            or tool.arguments
        )
        plus = _plus_lines(patch)
        return plus if plus else patch
    cmd = command(tool)
    hay = cmd if BEGIN_PATCH in cmd else (tool.arguments if BEGIN_PATCH in tool.arguments else "")
    if hay:
        plus = _plus_lines(hay)
        return plus if plus else hay
    return ""


def write_path(tool: ToolCall) -> str:
    args = tool.args_dict()
    path = args.get("path") or args.get("file_path") or args.get("target_file") or ""
    if path:
        return str(path)
    cmd = command(tool)
    for line in cmd.splitlines():
        stripped = line.strip()
        if stripped.startswith("*** Update File:"):
            return stripped.split(":", 1)[1].strip()
        if stripped.startswith("*** Add File:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def is_write_tool(tool: ToolCall) -> bool:
    name = tool.name.lower()
    if name in WRITE_TOOLS:
        return True
    return BEGIN_PATCH in command(tool) or BEGIN_PATCH in (tool.arguments or "")


def http_status(tool: ToolCall) -> Optional[int]:
    """Last HTTP status in the tool result, or -1 for a connection failure."""
    text = tool.result or ""
    codes = [int(m.group(1)) for m in HTTP_STATUS.finditer(text)]
    if codes:
        return codes[-1]
    if HTTP_CONNECT_FAIL.search(text):
        return -1
    return None


def is_http_tool(tool: ToolCall) -> bool:
    if HTTP_TOOL.search(command(tool)) or HTTP_TOOL.search(tool.arguments or ""):
        return True
    if HTTP_STATUS.search(tool.result or ""):
        return True
    if HTTP_CONNECT_FAIL.search(tool.result or "") and HTTP_TOOL.search(blob(tool)):
        return True
    return False


def http_bad(tool: ToolCall) -> bool:
    code = http_status(tool)
    if code is None:
        return False
    if code < 0:
        return True
    return code >= 400


COMMIT_CMD = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*commit\b")


def is_ship_mutate(tool: ToolCall) -> bool:
    """A tool that can change what a later live check would see."""
    if is_write_tool(tool):
        return True
    if failed(tool):
        return False
    hay = command(tool) + "\n" + (tool.arguments or "")
    return bool(SHIP_MUTATE.search(hay) or COMMIT_CMD.search(hay))
