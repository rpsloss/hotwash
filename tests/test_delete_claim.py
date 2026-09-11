import json
from pathlib import Path

from hotwash.detectors.delete_claim import run as delete_claim_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _trace(assistant: str, tools=None) -> Trace:
    tools = list(tools or [])
    return Trace(
        source="mem",
        messages=[
            Message(role="user", content="please delete the leftover file"),
            Message(role="assistant", content=assistant, tool_calls=tools),
        ],
        tools=tools,
    )


def _rm(cmd: str = "rm a.py", outcome: str = "success", result: str = "ok") -> ToolCall:
    return ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=json.dumps({"command": cmd}),
        result=result,
        outcome=outcome,
    )


def _named(name: str, outcome: str = "success") -> ToolCall:
    return ToolCall(
        id="c1",
        name=name,
        arguments=json.dumps({"path": "a.py"}),
        result="deleted a.py",
        outcome=outcome,
    )


def test_delete_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "delete_claim.jsonl")
    findings = delete_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "delete_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a file delete with no delete tool"


def test_delete_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "delete_claim_ok.jsonl")
    assert delete_claim_run(trace) == []


def test_i_deleted_is_error():
    findings = delete_claim_run(_trace("I deleted it."))
    assert len(findings) == 1
    assert findings[0].detector == "delete_claim"
    assert findings[0].severity == "error"


def test_i_removed_the_file_is_error():
    findings = delete_claim_run(_trace("I removed the file."))
    assert len(findings) == 1
    assert findings[0].detector == "delete_claim"
    assert findings[0].severity == "error"


def test_each_claim_phrase_is_error():
    for text in (
        "I deleted the file.",
        "I removed the file.",
        "deleted src/app.py",
        "removed src/app.py",
        "I deleted src/app.py",
    ):
        findings = delete_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "delete_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a file delete with no delete tool"


def test_i_will_delete_is_silent():
    assert delete_claim_run(_trace("I will delete the file.")) == []
    assert delete_claim_run(_trace("I will delete src/app.py")) == []


def test_ill_remove_is_silent():
    assert delete_claim_run(_trace("I'll remove the file.")) == []
    assert delete_claim_run(_trace("I'll remove src/app.py")) == []


def test_failed_delete_tool_still_errors():
    findings = delete_claim_run(_trace("I deleted the file.", [_named("delete_file", outcome="error")]))
    assert len(findings) == 1
    assert findings[0].detector == "delete_claim"
    assert findings[0].severity == "error"


def test_failed_rm_still_errors():
    findings = delete_claim_run(
        _trace("I deleted the file.", [_rm(outcome="error", result="exit: 1")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "delete_claim"
    assert findings[0].severity == "error"


def test_delete_tools_count():
    for name in ("delete_file", "delete", "remove_file", "unlink"):
        assert delete_claim_run(_trace("I deleted the file.", [_named(name)])) == [], name


def test_rm_counts():
    assert delete_claim_run(_trace("I deleted the file.", [_rm()])) == []


def test_del_unlink_git_rm_commands_count():
    for cmd in ("del a.py", "unlink a.py", "git rm a.py"):
        assert delete_claim_run(_trace("I deleted the file.", [_rm(cmd=cmd)])) == [], cmd


def test_cmd_array_rm_counts():
    tool = ToolCall(
        id="c1",
        name="shell",
        arguments=json.dumps({"cmd": ["rm", "a.py"]}),
        result="ok",
        outcome="success",
    )
    assert delete_claim_run(_trace("I deleted the file.", [tool])) == []


def test_search_replace_does_not_count():
    tool = ToolCall(
        id="c1",
        name="search_replace",
        arguments=json.dumps(
            {"file_path": "a.py", "old_string": "x", "new_string": "y"}
        ),
        result="updated a.py",
        outcome="success",
    )
    findings = delete_claim_run(_trace("I deleted the file.", [tool]))
    assert findings
    assert findings[0].detector == "delete_claim"


def test_write_tool_does_not_count():
    tool = ToolCall(
        id="c1",
        name="write",
        arguments=json.dumps({"path": "a.py", "content": "x = 1\n"}),
        result="wrote a.py",
        outcome="success",
    )
    findings = delete_claim_run(_trace("I deleted the file.", [tool]))
    assert findings
    assert findings[0].detector == "delete_claim"


def test_no_claim_is_silent():
    assert delete_claim_run(_trace("Looking at the leftover file.")) == []
