import json
from pathlib import Path

from hotwash.detectors.lint_claim import run as lint_claim_run
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


def test_lint_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "lint_claim.jsonl")
    findings = lint_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "lint_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed lint is clean with no linter in the trace"


def test_lint_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "lint_claim_ok.jsonl")
    assert lint_claim_run(trace) == []


def test_claim_phrases_are_error():
    for text in (
        "lint is clean",
        "linter passed",
        "no lint errors",
        "ruff is clean",
        "eslint passed",
    ):
        findings = lint_claim_run(_trace("look at the repo", text))
        assert findings, text
        assert findings[0].detector == "lint_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed lint is clean with no linter in the trace"


def test_ask_phrases_are_warn():
    for text in (
        "run lint",
        "run ruff",
        "run eslint",
    ):
        findings = lint_claim_run(_trace(text, "Working on it."))
        assert findings, text
        assert findings[0].detector == "lint_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == "lint was requested; no linter in the trace"


def test_future_tense_silent_if_not_asked():
    assert lint_claim_run(_trace("look at the repo", "I will run lint.")) == []
    assert lint_claim_run(_trace("look at the repo", "I'll run ruff.")) == []


def test_failed_ruff_with_claim_is_error():
    tool = _cmd("ruff check .", outcome="error", result="exit: 1\nerror")
    findings = lint_claim_run(_trace("run lint", "lint is clean", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "lint_claim"
    assert findings[0].severity == "error"


def test_failed_ruff_with_ask_only_is_warn():
    tool = _cmd("ruff check .", outcome="error", result="exit: 1\nerror")
    findings = lint_claim_run(_trace("run lint", "Working on it.", [tool]))
    assert len(findings) == 1
    assert findings[0].detector == "lint_claim"
    assert findings[0].severity == "warn"


def test_pytest_is_not_lint():
    findings = lint_claim_run(
        _trace("run lint", "lint is clean", [_cmd("pytest")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "lint_claim"
    assert findings[0].severity == "error"


def test_no_ask_no_claim_silent():
    assert lint_claim_run(_trace("how does this repo work?", "Here is the layout.")) == []


def test_successful_lint_commands_are_silent():
    for cmd in (
        "ruff check .",
        "python -m ruff check src",
        "npx eslint .",
        "eslint src",
        "pylint pkg",
        "flake8",
        "npm run lint",
        "golangci-lint run",
    ):
        assert (
            lint_claim_run(_trace("run lint", "lint is clean", [_cmd(cmd)])) == []
        ), cmd


def test_cmd_array_ruff_is_silent():
    tool = ToolCall(
        id="c1",
        name="shell",
        arguments=json.dumps({"cmd": ["ruff", "check", "."]}),
        result="All checks passed!",
        outcome="success",
    )
    assert lint_claim_run(_trace("run lint", "lint is clean", [tool])) == []


def test_cmd_array_npm_run_lint_is_silent():
    tool = ToolCall(
        id="c1",
        name="shell",
        arguments=json.dumps({"cmd": ["npm", "run", "lint"]}),
        result="lint ok",
        outcome="success",
    )
    assert lint_claim_run(_trace("run lint", "eslint passed", [tool])) == []


def test_claim_takes_priority_over_ask():
    findings = lint_claim_run(_trace("run lint", "lint is clean"))
    assert len(findings) == 1
    assert findings[0].severity == "error"
