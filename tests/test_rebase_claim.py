import json
from pathlib import Path

from hotwash.detectors.rebase_claim import run as rebase_claim_run
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


def test_rebase_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "rebase_claim.jsonl")
    findings = rebase_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "rebase_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a git rebase that is not in the trace"


def test_rebase_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "rebase_claim_ok.jsonl")
    assert rebase_claim_run(trace) == []


def test_claim_phrases_are_error():
    for text in (
        "I rebased",
        "rebase succeeded",
        "rebased onto main",
    ):
        findings = rebase_claim_run(_trace("look at the repo", text))
        assert findings, text
        assert findings[0].detector == "rebase_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a git rebase that is not in the trace"


def test_ask_phrases_are_warn():
    for text in (
        "rebase onto main",
        "git rebase",
        "rebase this branch",
    ):
        findings = rebase_claim_run(_trace(text, "Working on it."))
        assert findings, text
        assert findings[0].detector == "rebase_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "a rebase was requested; no git rebase in the trace"


def test_future_tense_silent_if_not_asked():
    assert rebase_claim_run(_trace("look at the repo", "I will rebase")) == []
    assert rebase_claim_run(_trace("look at the repo", "I'll rebase")) == []


def test_failed_git_rebase_with_claim_is_error():
    tool = _cmd("git rebase main", outcome="error", result="exit: 1\nCONFLICT")
    findings = rebase_claim_run(_trace("rebase onto main", "I rebased", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "rebase_claim"
    assert findings[0].severity == "error"


def test_failed_git_rebase_with_ask_only_is_warn():
    tool = _cmd("git rebase main", outcome="error", result="exit: 1\nCONFLICT")
    findings = rebase_claim_run(_trace("rebase onto main", "Working on it.", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "rebase_claim"
    assert findings[0].severity == "warn"


def test_exit_code_fail_does_not_count():
    tool = _cmd("git rebase main", outcome="success", result="exit: 1\nfatal")
    findings = rebase_claim_run(_trace("rebase onto main", "I rebased", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_git_merge_is_not_rebase():
    findings = rebase_claim_run(
        _trace("rebase onto main", "I rebased", [_cmd("git merge main")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "rebase_claim"
    assert findings[0].severity == "error"


def test_successful_rebase_commands_are_silent():
    for cmd in (
        "git rebase main",
        "git rebase origin/main",
        "git rebase --continue",
        "git rebase --abort",
    ):
        assert (
            rebase_claim_run(_trace("rebase onto main", "I rebased", [_cmd(cmd)])) == []
        ), cmd


def test_cmd_array_git_rebase_counts():
    tool = _cmd(["git", "rebase", "main"], result="Successfully rebased.")
    assert rebase_claim_run(_trace("rebase onto main", "I rebased", [tool])) == []


def test_claim_takes_priority_over_ask():
    findings = rebase_claim_run(_trace("rebase onto main", "I rebased"))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_ask_with_successful_rebase_is_silent():
    tool = _cmd("git rebase main")
    assert (
        rebase_claim_run(_trace("rebase onto main", "Working on it.", [tool])) == []
    )


def test_no_ask_no_claim_silent():
    assert rebase_claim_run(_trace("how does this repo work?", "Here is the layout.")) == []
