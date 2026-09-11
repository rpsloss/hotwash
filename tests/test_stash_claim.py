import json
from pathlib import Path

from hotwash.detectors.stash_claim import run as stash_claim_run
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


def test_stash_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "stash_claim.jsonl")
    findings = stash_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "stash_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a git stash that is not in the trace"


def test_stash_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "stash_claim_ok.jsonl")
    assert stash_claim_run(trace) == []


def test_each_claim_phrase_is_error():
    for text in (
        "I stashed",
        "stash succeeded",
        "changes are stashed",
        "stashed the work",
    ):
        findings = stash_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "stash_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a git stash that is not in the trace"


def test_ask_phrases_are_warn():
    for text in (
        "please git stash",
        "stash these changes",
        "stash the work",
    ):
        findings = stash_claim_run(_trace("Working on it.", user=text))
        assert findings, text
        assert findings[0].detector == "stash_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "a stash was requested; no git stash in the trace"


def test_future_tense_is_silent():
    assert stash_claim_run(_trace("I will stash")) == []
    assert stash_claim_run(_trace("I'll stash")) == []
    assert stash_claim_run(_trace("I will stash the work.")) == []


def test_failed_stash_still_fires():
    tool = _shell("git stash", outcome="error", result="exit: 1")
    findings = stash_claim_run(_trace("I stashed", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "stash_claim"
    assert findings[0].severity == "error"


def test_failed_stash_with_ask_only_is_warn():
    tool = _shell("git stash", outcome="error", result="exit: 1")
    findings = stash_claim_run(_trace("Working on it.", [tool], user="please git stash"))
    assert len(findings) == 1
    assert findings[0].detector == "stash_claim"
    assert findings[0].severity == "warn"


def test_exit_code_fail_does_not_count():
    tool = _shell("git stash", outcome="success", result="exit: 1\nfatal")
    findings = stash_claim_run(_trace("I stashed", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_git_status_is_not_stash():
    findings = stash_claim_run(_trace("I stashed", [_shell("git status")]))
    assert len(findings) == 1
    assert findings[0].detector == "stash_claim"
    assert findings[0].severity == "error"


def test_git_stash_counts():
    tool = _shell("git stash", result="Saved working directory and index state")
    assert stash_claim_run(_trace("I stashed", [tool])) == []


def test_git_stash_push_pop_apply_count():
    for cmd in (
        "git stash push -m wip",
        "git stash pop",
        "git stash apply",
    ):
        tool = _shell(cmd, result="ok")
        assert stash_claim_run(_trace("I stashed", [tool])) == [], cmd


def test_cmd_array_git_stash_counts():
    tool = _shell(["git", "stash"], result="Saved working directory and index state")
    assert stash_claim_run(_trace("I stashed", [tool])) == []


def test_ask_with_successful_stash_is_silent():
    tool = _shell("git stash")
    assert (
        stash_claim_run(_trace("Working on it.", [tool], user="please git stash"))
        == []
    )


def test_claim_takes_priority_over_ask():
    findings = stash_claim_run(_trace("I stashed", user="please git stash"))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_no_ask_no_claim_silent():
    assert stash_claim_run(_trace("Looking at the about page.")) == []
