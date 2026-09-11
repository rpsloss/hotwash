import json
from pathlib import Path

from hotwash.detectors.read_claim import run as read_claim_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _trace(assistant: str, tools=None) -> Trace:
    tools = list(tools or [])
    return Trace(
        source="mem",
        messages=[
            Message(role="user", content="please inspect the about page"),
            Message(role="assistant", content=assistant, tool_calls=tools),
        ],
        tools=tools,
    )


def _read_tool(name: str = "read_file", outcome: str = "success") -> ToolCall:
    return ToolCall(
        id="c1",
        name=name,
        arguments=json.dumps({"path": "a.py"}),
        result="x = 1\n",
        outcome=outcome,
    )


def _shell(cmd: str, outcome: str = "success", result: str = "x = 1") -> ToolCall:
    return ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=json.dumps({"command": cmd}),
        result=result,
        outcome=outcome,
    )


def test_read_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "read_claim.jsonl")
    findings = read_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "read_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a file read with no read tool"


def test_read_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "read_claim_ok.jsonl")
    assert read_claim_run(trace) == []


def test_i_read_the_file_is_error():
    findings = read_claim_run(_trace("I read the file."))
    assert len(findings) == 1
    assert findings[0].detector == "read_claim"
    assert findings[0].severity == "error"


def test_each_claim_phrase_is_error():
    for text in (
        "I read src/app.py",
        "I opened src/app.py",
        "I inspected src/app.py",
        "I looked at src/app.py",
        "I read `src/app.py`",
        "I read the file src/app.py",
        "I read the file a.py",
    ):
        findings = read_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "read_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a file read with no read tool"


def test_i_will_read_is_silent():
    assert read_claim_run(_trace("I will read src/app.py")) == []
    assert read_claim_run(_trace("I will read the file.")) == []


def test_ill_look_at_is_silent():
    assert read_claim_run(_trace("I'll look at src/app.py")) == []
    assert read_claim_run(_trace("I'll look at the file.")) == []


def test_ill_read_is_silent():
    assert read_claim_run(_trace("I'll read src/app.py")) == []
    assert read_claim_run(_trace("I'll read the file.")) == []


def test_according_to_path_is_silent():
    assert read_claim_run(_trace("according to src/app.py")) == []
    assert read_claim_run(_trace("According to `src/app.py`, the handler is wired.")) == []


def test_failed_read_tool_still_errors():
    findings = read_claim_run(_trace("I read src/app.py", [_read_tool(outcome="error")]))
    assert len(findings) == 1
    assert findings[0].detector == "read_claim"
    assert findings[0].severity == "error"


def test_read_file_counts():
    assert read_claim_run(_trace("I read src/app.py", [_read_tool()])) == []


def test_read_counts():
    assert read_claim_run(_trace("I read src/app.py", [_read_tool(name="read")])) == []


def test_readfile_counts():
    assert read_claim_run(_trace("I read src/app.py", [_read_tool(name="readfile")])) == []


def test_cat_counts_as_read():
    assert read_claim_run(_trace("I read src/app.py", [_shell("cat src/app.py")])) == []


def test_windows_type_counts_as_read():
    assert read_claim_run(_trace("I read src/app.py", [_shell("type src\\app.py")])) == []


def test_failed_cat_still_errors():
    findings = read_claim_run(
        _trace("I read src/app.py", [_shell("cat src/app.py", outcome="error")])
    )
    assert findings
    assert findings[0].detector == "read_claim"


def test_write_tool_does_not_count():
    tool = ToolCall(
        id="c1",
        name="write",
        arguments=json.dumps({"path": "a.py", "content": "x = 1\n"}),
        result="wrote a.py",
        outcome="success",
    )
    findings = read_claim_run(_trace("I read src/app.py", [tool]))
    assert findings
    assert findings[0].detector == "read_claim"


def test_no_claim_is_silent():
    assert read_claim_run(_trace("Looking at the about page.")) == []
