import json
from pathlib import Path

from hotwash.detectors.write_claim import run as write_claim_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _trace(assistant: str, tools=None) -> Trace:
    tools = list(tools or [])
    return Trace(
        source="mem",
        messages=[
            Message(role="user", content="please update the about page"),
            Message(role="assistant", content=assistant, tool_calls=tools),
        ],
        tools=tools,
    )


def _write(name: str = "write", outcome: str = "success") -> ToolCall:
    return ToolCall(
        id="c1",
        name=name,
        arguments=json.dumps({"path": "a.py", "content": "x = 1\n"}),
        result="wrote a.py",
        outcome=outcome,
    )


def test_write_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "write_claim.jsonl")
    findings = write_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "write_claim"
    assert findings[0].severity == "error"
    assert "write" in findings[0].title


def test_write_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "write_claim_ok.jsonl")
    assert write_claim_run(trace) == []


def test_i_updated_the_file_is_error():
    findings = write_claim_run(_trace("I updated the file."))
    assert len(findings) == 1
    assert findings[0].detector == "write_claim"
    assert findings[0].severity == "error"


def test_i_wrote_created_edited_saved_the_file_is_error():
    for text in (
        "I wrote the file.",
        "I created the file.",
        "I edited the file.",
        "I saved the file.",
    ):
        findings = write_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "write_claim"
        assert findings[0].severity == "error"


def test_updated_path_is_error():
    findings = write_claim_run(_trace("updated src/app.py"))
    assert len(findings) == 1
    assert findings[0].detector == "write_claim"


def test_wrote_path_is_error():
    findings = write_claim_run(_trace("wrote a.py"))
    assert findings
    assert findings[0].severity == "error"


def test_changes_are_in_path_is_error():
    findings = write_claim_run(_trace("The changes are in src/app.py"))
    assert len(findings) == 1
    assert findings[0].detector == "write_claim"


def test_i_will_write_is_silent():
    assert write_claim_run(_trace("I will write the file.")) == []
    assert write_claim_run(_trace("I will write src/app.py")) == []


def test_ill_edit_is_silent():
    assert write_claim_run(_trace("I'll edit the file.")) == []
    assert write_claim_run(_trace("I'll edit src/app.py")) == []


def test_failed_write_tool_still_errors():
    findings = write_claim_run(_trace("I updated the file.", [_write(outcome="error")]))
    assert len(findings) == 1
    assert findings[0].detector == "write_claim"
    assert findings[0].severity == "error"


def test_search_replace_counts_as_write():
    tool = ToolCall(
        id="c1",
        name="search_replace",
        arguments=json.dumps(
            {"file_path": "a.py", "old_string": "x", "new_string": "y"}
        ),
        result="updated a.py",
        outcome="success",
    )
    assert write_claim_run(_trace("I updated the file.", [tool])) == []


def test_apply_patch_counts_as_write():
    patch = "*** Begin Patch\n*** Add File: a.py\n+x = 1\n*** End Patch"
    tool = ToolCall(
        id="c1",
        name="apply_patch",
        arguments=patch,
        result="ok",
        outcome="success",
    )
    assert write_claim_run(_trace("I wrote the file.", [tool])) == []


def test_non_write_tool_does_not_count():
    tool = ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=json.dumps({"command": "cat src/app.py"}),
        result="x = 1",
        outcome="success",
    )
    findings = write_claim_run(_trace("I updated the file.", [tool]))
    assert findings
    assert findings[0].detector == "write_claim"


def test_no_claim_is_silent():
    assert write_claim_run(_trace("Looking at the about page.")) == []


def test_about_is_updated_is_silent():
    assert write_claim_run(_trace("About is updated.")) == []
