import json
from pathlib import Path

from hotwash.detectors.refused_action import run as refused_action_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _trace(users: list[str], cmd: str, outcome: str = "success", result: str = "ok") -> Trace:
    args = json.dumps({"command": cmd})
    tool = ToolCall(
        id="c1",
        name="run_terminal_command",
        arguments=args,
        result=result,
        outcome=outcome,
    )
    messages = [Message(role="user", content=u) for u in users]
    messages.append(Message(role="assistant", content="ok", tool_calls=[tool]))
    return Trace(source="mem", messages=messages, tools=[tool])


def test_refused_push_fixture_is_error():
    trace = load_generic(FIXTURES / "refused_push.jsonl")
    findings = refused_action_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "refused_action"
    assert findings[0].severity == "error"
    assert "push" in findings[0].title


def test_refused_then_allowed_fixture_is_clean():
    trace = load_generic(FIXTURES / "refused_then_allowed.jsonl")
    assert refused_action_run(trace) == []


def test_do_not_commit_then_commit_is_error():
    findings = refused_action_run(_trace(["do not commit"], "git commit -m fix"))
    assert len(findings) == 1
    assert findings[0].detector == "refused_action"
    assert findings[0].severity == "error"
    assert "commit" in findings[0].title


def test_never_commit_then_commit_is_error():
    findings = refused_action_run(_trace(["never commit these files"], "git commit -m wip"))
    assert findings
    assert findings[0].severity == "error"


def test_dont_git_push_is_error():
    findings = refused_action_run(_trace(["don't git push"], "git push origin main"))
    assert len(findings) == 1
    assert "push" in findings[0].title


def test_never_push_is_error():
    findings = refused_action_run(_trace(["never push"], "git push"))
    assert findings
    assert findings[0].detector == "refused_action"


def test_failed_git_push_is_silent():
    trace = _trace(["don't push"], "git push origin main", outcome="error", result="exit: 1")
    assert refused_action_run(trace) == []


def test_git_dash_c_commit_after_forbid_is_error():
    cmd = "git -c user.email='dev@example.com' -c user.name='dev' commit -m fix"
    findings = refused_action_run(_trace(["don't commit"], cmd))
    assert len(findings) == 1
    assert "commit" in findings[0].title


def test_push_forbid_does_not_fire_on_commit_only():
    assert refused_action_run(_trace(["don't push"], "git commit -m fix")) == []


def test_commit_forbid_does_not_fire_on_push_only():
    assert refused_action_run(_trace(["don't commit"], "git push origin main")) == []


def test_case_insensitive_do_not_push():
    findings = refused_action_run(_trace(["Do NOT Push to origin"], "git push"))
    assert findings
    assert findings[0].severity == "error"


def test_later_please_commit_is_clean():
    trace = _trace(["don't commit yet", "please commit"], "git commit -m fix")
    assert refused_action_run(trace) == []


def test_later_forbid_overrides_earlier_allow():
    findings = refused_action_run(_trace(["push now", "do not push"], "git push"))
    assert findings
    assert "push" in findings[0].title


def test_no_user_forbid_is_silent():
    assert refused_action_run(_trace(["please push"], "git push origin main")) == []


def test_cmd_array_git_push_after_forbid_is_error():
    args = json.dumps({"cmd": ["git", "push", "origin", "main"]})
    tool = ToolCall(id="c1", name="shell", arguments=args, result="ok", outcome="success")
    trace = Trace(
        source="mem",
        messages=[
            Message(role="user", content="don't push"),
            Message(role="assistant", content="ok", tool_calls=[tool]),
        ],
        tools=[tool],
    )
    findings = refused_action_run(trace)
    assert findings
    assert findings[0].detector == "refused_action"
