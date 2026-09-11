import json
from pathlib import Path

from hotwash.detectors.merge_claim import run as merge_claim_run
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


def test_merge_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "merge_claim.jsonl")
    findings = merge_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "merge_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a merge with no git merge / gh pr merge"


def test_merge_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "merge_claim_ok.jsonl")
    assert merge_claim_run(trace) == []


def test_claim_phrases_are_error():
    for text in (
        "I merged",
        "merge is done",
        "merged into main",
        "PR is merged",
    ):
        findings = merge_claim_run(_trace("look at the repo", text))
        assert findings, text
        assert findings[0].detector == "merge_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a merge with no git merge / gh pr merge"


def test_ask_phrases_are_warn():
    for text in (
        "please merge",
        "merge this PR",
        "git merge",
    ):
        findings = merge_claim_run(_trace(text, "Working on it."))
        assert findings, text
        assert findings[0].detector == "merge_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "a merge was requested; no merge command in the trace"


def test_future_tense_silent_if_not_asked():
    assert merge_claim_run(_trace("look at the repo", "I will merge")) == []
    assert merge_claim_run(_trace("look at the repo", "I'll merge")) == []


def test_failed_git_merge_with_claim_is_error():
    tool = _cmd("git merge feat", outcome="error", result="exit: 1\nCONFLICT")
    findings = merge_claim_run(_trace("please merge", "I merged", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "merge_claim"
    assert findings[0].severity == "error"


def test_failed_git_merge_with_ask_only_is_warn():
    tool = _cmd("git merge feat", outcome="error", result="exit: 1\nCONFLICT")
    findings = merge_claim_run(_trace("please merge", "Working on it.", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "merge_claim"
    assert findings[0].severity == "warn"


def test_exit_code_fail_does_not_count():
    tool = _cmd("git merge feat", outcome="success", result="exit: 1\nfatal")
    findings = merge_claim_run(_trace("please merge", "I merged", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_git_status_is_not_merge():
    findings = merge_claim_run(
        _trace("please merge", "I merged", [_cmd("git status")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "merge_claim"
    assert findings[0].severity == "error"


def test_successful_merge_commands_are_silent():
    for cmd in (
        "git merge feat",
        "git merge origin/main",
        "gh pr merge",
        "gh pr merge 12",
        "hub merge 12",
    ):
        assert (
            merge_claim_run(_trace("please merge", "I merged", [_cmd(cmd)])) == []
        ), cmd


def test_cmd_array_git_merge_counts():
    tool = _cmd(["git", "merge", "feat"], result="Merge made by the 'ort' strategy.")
    assert merge_claim_run(_trace("please merge", "I merged", [tool])) == []


def test_cmd_array_gh_pr_merge_counts():
    tool = _cmd(["gh", "pr", "merge", "12"], result="Merged")
    assert merge_claim_run(_trace("merge this PR", "PR is merged", [tool])) == []


def test_claim_takes_priority_over_ask():
    findings = merge_claim_run(_trace("please merge", "I merged"))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_ask_with_successful_merge_is_silent():
    tool = _cmd("git merge feat")
    assert (
        merge_claim_run(_trace("please merge", "Working on it.", [tool])) == []
    )


def test_no_ask_no_claim_silent():
    assert merge_claim_run(_trace("how does this repo work?", "Here is the layout.")) == []
