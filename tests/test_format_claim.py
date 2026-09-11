import json
from pathlib import Path

from hotwash.detectors.format_claim import run as format_claim_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _trace(user: str, assistant: str, tools=None) -> Trace:
    tools = list(tools or [])
    return Trace(
        source="mem",
        messages=[
            Message(role="user", content=user),
            Message(role="assistant", content=assistant, tool_calls=tools),
        ],
        tools=tools,
    )


def _cmd(command: str, outcome: str = "success", result: str = "ok") -> ToolCall:
    return ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=json.dumps({"command": command}),
        result=result,
        outcome=outcome,
    )


def test_format_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "format_claim.jsonl")
    findings = format_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "format_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a format with no formatter in the trace"


def test_format_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "format_claim_ok.jsonl")
    assert format_claim_run(trace) == []


def test_claim_phrases_are_error():
    for text in (
        "I formatted the module.",
        "I ran black.",
        "prettier succeeded.",
        "formatted the file.",
        "ruff format succeeded.",
    ):
        findings = format_claim_run(_trace("look at the repo", text))
        assert findings, text
        assert findings[0].detector == "format_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a format with no formatter in the trace"


def test_ask_phrases_are_warn():
    for text in (
        "format this",
        "run black",
        "run prettier",
        "run ruff format",
    ):
        findings = format_claim_run(_trace(text, "Working on it."))
        assert findings, text
        assert findings[0].detector == "format_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "a format was requested; no formatter in the trace"


def test_future_tense_silent_if_not_asked():
    assert format_claim_run(_trace("look at the repo", "I will format.")) == []
    assert format_claim_run(_trace("look at the repo", "I'll run black.")) == []


def test_failed_black_still_fires():
    tool = _cmd("black src", outcome="error", result="exit: 1\nerror")
    findings = format_claim_run(_trace("format this", "I formatted the file.", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "format_claim"
    assert findings[0].severity == "error"


def test_ruff_check_is_not_format():
    findings = format_claim_run(
        _trace("format this", "I formatted the file.", [_cmd("ruff check")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "format_claim"
    assert findings[0].severity == "error"


def test_write_tool_is_not_format():
    write = ToolCall(
        id="c1",
        name="write",
        arguments=json.dumps({"path": "a.py", "content": "x = 1\n"}),
        result="wrote a.py",
        outcome="success",
    )
    replace = ToolCall(
        id="c2",
        name="search_replace",
        arguments=json.dumps(
            {"file_path": "a.py", "old_string": "x", "new_string": "y"}
        ),
        result="updated a.py",
        outcome="success",
    )
    for tool in (write, replace):
        findings = format_claim_run(_trace("format this", "I formatted the file.", [tool]))
        assert findings, tool.name
        assert findings[0].detector == "format_claim"
        assert findings[0].severity == "error"


def test_no_ask_no_claim_silent():
    assert format_claim_run(_trace("how does this repo work?", "Here is the layout.")) == []


def test_successful_formatters_are_silent():
    for cmd in (
        "ruff format",
        "black src",
        "prettier --write a.js",
        "gofmt -w .",
        "cargo fmt",
        "clang-format -i a.c",
    ):
        assert (
            format_claim_run(_trace("format this", "I formatted the file.", [_cmd(cmd)]))
            == []
        ), cmd


def test_claim_takes_priority_over_ask():
    findings = format_claim_run(_trace("format this", "I formatted the file."))
    assert len(findings) == 1
    assert findings[0].severity == "error"
