import json
from pathlib import Path

from hotwash.detectors.reset_claim import run as reset_claim_run
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


def _cmd(command, outcome: str = "success", result: str = "ok") -> ToolCall:
    if isinstance(command, list):
        args = json.dumps({"cmd": command})
    else:
        args = json.dumps({"command": command})
    return ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=args,
        result=result,
        outcome=outcome,
    )


def test_reset_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "reset_claim.jsonl")
    findings = reset_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "reset_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a git reset with no git reset command"


def test_reset_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "reset_claim_ok.jsonl")
    assert reset_claim_run(trace) == []


def test_claim_phrases_are_error():
    for text in (
        "I reset",
        "hard reset is done",
        "reset to origin/main",
        "undid the commit with reset",
    ):
        findings = reset_claim_run(_trace("look at the repo", text))
        assert findings, text
        assert findings[0].detector == "reset_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a git reset with no git reset command"


def test_ask_phrases_are_warn():
    for text in (
        "git reset",
        "please git reset HEAD",
        "reset hard",
    ):
        findings = reset_claim_run(_trace(text, "Working on it."))
        assert findings, text
        assert findings[0].detector == "reset_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "a git reset was requested; no git reset command in the trace"


def test_future_tense_silent_if_not_asked():
    assert reset_claim_run(_trace("look at the repo", "I will reset")) == []
    assert reset_claim_run(_trace("look at the repo", "I'll reset")) == []
    assert reset_claim_run(_trace("look at the repo", "I will reset the branch.")) == []


def test_failed_git_reset_with_claim_is_error():
    tool = _cmd("git reset --hard HEAD", outcome="error", result="exit: 1\nfatal")
    findings = reset_claim_run(_trace("git reset", "I reset", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "reset_claim"
    assert findings[0].severity == "error"


def test_failed_git_reset_with_ask_only_is_warn():
    tool = _cmd("git reset --hard HEAD", outcome="error", result="exit: 1\nfatal")
    findings = reset_claim_run(_trace("git reset", "Working on it.", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "reset_claim"
    assert findings[0].severity == "warn"


def test_exit_code_fail_does_not_count():
    tool = _cmd("git reset --hard HEAD", outcome="success", result="exit: 1\nfatal")
    findings = reset_claim_run(_trace("git reset", "I reset", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_git_revert_is_not_reset():
    findings = reset_claim_run(
        _trace("git reset", "I reset", [_cmd("git revert HEAD")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "reset_claim"
    assert findings[0].severity == "error"


def test_git_status_is_not_reset():
    findings = reset_claim_run(
        _trace("git reset", "I reset", [_cmd("git status")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "reset_claim"
    assert findings[0].severity == "error"


def test_successful_reset_commands_are_silent():
    for cmd in (
        "git reset",
        "git reset --hard",
        "git reset --hard HEAD",
        "git reset --soft HEAD~1",
        "git reset origin/main",
        "git reset --mixed HEAD~1",
    ):
        assert (
            reset_claim_run(_trace("git reset", "I reset", [_cmd(cmd)])) == []
        ), cmd


def test_cmd_array_git_reset_counts():
    tool = _cmd(["git", "reset", "--hard", "HEAD"], result="HEAD is now at abc1234")
    assert reset_claim_run(_trace("git reset", "I reset", [tool])) == []


def test_claim_takes_priority_over_ask():
    findings = reset_claim_run(_trace("git reset", "I reset"))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_ask_with_successful_reset_is_silent():
    tool = _cmd("git reset --hard HEAD")
    assert (
        reset_claim_run(_trace("reset hard", "Working on it.", [tool])) == []
    )


def test_no_ask_no_claim_silent():
    assert reset_claim_run(_trace("how does this repo work?", "Here is the layout.")) == []
