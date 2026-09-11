import json
from pathlib import Path

from hotwash.detectors.tag_claim import run as tag_claim_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _trace(assistant: str, tools=None, user: str = "please inspect the about page") -> Trace:
    tools = list(tools or [])
    return Trace(
        source="mem",
        messages=[
            Message(role="user", content=user),
            Message(role="assistant", content=assistant, tool_calls=tools),
        ],
        tools=tools,
    )


def _shell(cmd, outcome: str = "success", result: str = "ok") -> ToolCall:
    if isinstance(cmd, list):
        args = json.dumps({"cmd": cmd})
    else:
        args = json.dumps({"command": cmd})
    return ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=args,
        result=result,
        outcome=outcome,
    )


def test_tag_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "tag_claim.jsonl")
    findings = tag_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "tag_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a git tag with no git tag command"


def test_tag_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "tag_claim_ok.jsonl")
    assert tag_claim_run(trace) == []


def test_each_claim_phrase_is_error():
    for text in (
        "I tagged",
        "created a tag",
        "tag is pushed",
        "v1.0 is tagged",
    ):
        findings = tag_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "tag_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a git tag with no git tag command"


def test_git_tag_ask_is_warn():
    findings = tag_claim_run(_trace("Working on it.", user="please git tag v1.0"))
    assert len(findings) == 1
    assert findings[0].detector == "tag_claim"
    assert findings[0].severity == "warn"
    assert "tag" in findings[0].title


def test_create_a_tag_ask_is_warn():
    findings = tag_claim_run(_trace("Working on it.", user="please create a tag"))
    assert len(findings) == 1
    assert findings[0].detector == "tag_claim"
    assert findings[0].severity == "warn"


def test_tag_this_release_ask_is_warn():
    findings = tag_claim_run(_trace("Working on it.", user="tag this release"))
    assert len(findings) == 1
    assert findings[0].detector == "tag_claim"
    assert findings[0].severity == "warn"


def test_git_tag_counts():
    tool = _shell("git tag v1.0", result="tagged v1.0")
    assert tag_claim_run(_trace("I tagged", [tool])) == []


def test_git_tag_annotate_counts():
    tool = _shell("git tag -a v1.0 -m release", result="")
    assert tag_claim_run(_trace("created a tag", [tool])) == []


def test_failed_git_tag_still_errors():
    tool = _shell("git tag v1.0", outcome="error", result="exit: 1")
    findings = tag_claim_run(_trace("I tagged", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "tag_claim"
    assert findings[0].severity == "error"


def test_exit_code_fail_does_not_count():
    tool = _shell("git tag v1.0", outcome="success", result="exit: 1\nfatal")
    findings = tag_claim_run(_trace("I tagged", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_cmd_array_git_tag_counts():
    tool = _shell(["git", "tag", "v1.0"], result="tagged v1.0")
    assert tag_claim_run(_trace("I tagged", [tool])) == []


def test_git_push_tags_does_not_count():
    tool = _shell("git push --tags", result="ok")
    findings = tag_claim_run(_trace("tag is pushed", [tool]))
    assert findings
    assert findings[0].detector == "tag_claim"
    assert findings[0].severity == "error"


def test_ask_with_successful_tag_is_silent():
    tool = _shell("git tag v1.0")
    assert (
        tag_claim_run(_trace("Working on it.", [tool], user="please create a tag"))
        == []
    )


def test_i_will_tag_is_silent():
    assert tag_claim_run(_trace("I will tag")) == []
    assert tag_claim_run(_trace("I'll tag")) == []
    assert tag_claim_run(_trace("I will tag this release.")) == []


def test_claim_takes_priority_over_ask():
    findings = tag_claim_run(_trace("I tagged", user="please create a tag"))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_no_claim_or_ask_is_silent():
    assert tag_claim_run(_trace("Looking at the about page.")) == []
