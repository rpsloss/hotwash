import json
from pathlib import Path

from hotwash.detectors.revert_claim import run as revert_claim_run
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


def test_revert_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "revert_claim.jsonl")
    findings = revert_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "revert_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a git revert that is not in the trace"


def test_revert_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "revert_claim_ok.jsonl")
    assert revert_claim_run(trace) == []


def test_ask_only_is_warn():
    for text in (
        "revert that commit",
        "please git revert HEAD",
        "undo that commit with revert",
    ):
        findings = revert_claim_run(_trace("Working on it.", user=text))
        assert findings, text
        assert findings[0].detector == "revert_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "a revert was requested; no git revert in the trace"


def test_claim_is_error():
    for text in (
        "I reverted",
        "revert succeeded",
        "reverted the commit",
    ):
        findings = revert_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "revert_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a git revert that is not in the trace"


def test_future_tense_is_silent():
    assert revert_claim_run(_trace("I will revert")) == []
    assert revert_claim_run(_trace("I'll revert")) == []
    assert revert_claim_run(_trace("I will revert that commit.")) == []


def test_failed_revert_still_fires():
    tool = _shell("git revert HEAD", outcome="error", result="exit: 1\nerror: commit is a merge")
    findings = revert_claim_run(_trace("I reverted", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "revert_claim"
    assert findings[0].severity == "error"


def test_git_reset_is_not_revert():
    tool = _shell("git reset --hard HEAD~1", result="HEAD is now at abc1234")
    findings = revert_claim_run(_trace("I reverted", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "revert_claim"
    assert findings[0].severity == "error"


def test_no_ask_no_claim_silent():
    assert revert_claim_run(_trace("Looking at the about page.")) == []


def test_i_undid_the_edit_is_silent():
    assert revert_claim_run(_trace("I undid the edit")) == []


def test_successful_git_revert_is_silent():
    tool = _shell("git revert HEAD", result='[main abc1234] Revert "bad commit"')
    assert revert_claim_run(_trace("I reverted", [tool])) == []


def test_cmd_array_git_revert_counts():
    tool = _shell(["git", "revert", "HEAD"], result='[main abc1234] Revert "bad"')
    assert revert_claim_run(_trace("I reverted", [tool])) == []


def test_exit_code_fail_does_not_count():
    tool = _shell("git revert HEAD", outcome="success", result="exit: 1\nfatal")
    findings = revert_claim_run(_trace("I reverted", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_claim_takes_priority_over_ask():
    findings = revert_claim_run(_trace("I reverted", user="revert that commit"))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_ask_with_successful_revert_is_silent():
    tool = _shell("git revert HEAD")
    assert (
        revert_claim_run(_trace("Working on it.", [tool], user="revert that commit"))
        == []
    )


def test_failed_revert_ask_only_is_warn():
    tool = _shell("git revert HEAD", outcome="error", result="exit: 1")
    findings = revert_claim_run(_trace("Working on it.", [tool], user="git revert HEAD"))
    assert len(findings) == 1
    assert findings[0].detector == "revert_claim"
    assert findings[0].severity == "warn"
