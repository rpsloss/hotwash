import json
from pathlib import Path

from hotwash.detectors.branch_claim import run as branch_claim_run
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


def test_branch_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "branch_claim.jsonl")
    findings = branch_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "branch_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a git branch with no branch command"


def test_branch_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "branch_claim_ok.jsonl")
    assert branch_claim_run(trace) == []


def test_each_claim_phrase_is_error():
    for text in (
        "I created a branch",
        "checked out a new branch",
        "branch is ready",
        "switched to branch",
    ):
        findings = branch_claim_run(_trace(text))
        assert findings, text
        assert findings[0].detector == "branch_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a git branch with no branch command"


def test_create_a_branch_ask_is_warn():
    findings = branch_claim_run(_trace("Working on it.", user="please create a branch"))
    assert len(findings) == 1
    assert findings[0].detector == "branch_claim"
    assert findings[0].severity == "warn"
    assert "branch" in findings[0].title


def test_git_checkout_dash_b_ask_is_warn():
    findings = branch_claim_run(_trace("Working on it.", user="git checkout -b feat"))
    assert len(findings) == 1
    assert findings[0].detector == "branch_claim"
    assert findings[0].severity == "warn"


def test_git_checkout_b_counts():
    tool = _shell("git checkout -b feat", result="Switched to a new branch 'feat'")
    assert branch_claim_run(_trace("I created a branch", [tool])) == []


def test_git_switch_c_counts():
    tool = _shell("git switch -c feat", result="Switched to a new branch 'feat'")
    assert branch_claim_run(_trace("I created a branch", [tool])) == []


def test_git_branch_name_counts():
    tool = _shell("git branch feat", result="")
    assert branch_claim_run(_trace("I created a branch", [tool])) == []


def test_git_branch_dash_d_does_not_count():
    tool = _shell("git branch -d feat", result="Deleted branch feat")
    findings = branch_claim_run(_trace("I created a branch", [tool]))
    assert findings
    assert findings[0].detector == "branch_claim"
    assert findings[0].severity == "error"


def test_git_checkout_without_b_does_not_count():
    tool = _shell("git checkout feat", result="Switched to branch 'feat'")
    findings = branch_claim_run(_trace("switched to branch", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_git_switch_without_c_does_not_count():
    tool = _shell("git switch feat", result="Switched to branch 'feat'")
    findings = branch_claim_run(_trace("switched to branch", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_failed_checkout_b_still_errors():
    tool = _shell("git checkout -b feat", outcome="error", result="exit: 1")
    findings = branch_claim_run(_trace("I created a branch", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "branch_claim"
    assert findings[0].severity == "error"


def test_exit_code_fail_does_not_count():
    tool = _shell("git checkout -b feat", outcome="success", result="exit: 1\nfatal")
    findings = branch_claim_run(_trace("I created a branch", [tool]))
    assert findings
    assert findings[0].severity == "error"


def test_cmd_array_checkout_b_counts():
    tool = _shell(["git", "checkout", "-b", "feat"], result="Switched to a new branch 'feat'")
    assert branch_claim_run(_trace("I created a branch", [tool])) == []


def test_ask_with_successful_branch_is_silent():
    tool = _shell("git checkout -b feat")
    assert (
        branch_claim_run(_trace("Working on it.", [tool], user="please create a branch"))
        == []
    )


def test_i_will_create_a_branch_is_silent():
    assert branch_claim_run(_trace("I will create a branch.")) == []
    assert branch_claim_run(_trace("I'll create a branch.")) == []


def test_no_claim_or_ask_is_silent():
    assert branch_claim_run(_trace("Looking at the about page.")) == []
