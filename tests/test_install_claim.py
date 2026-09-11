import json
from pathlib import Path

from hotwash.detectors.install_claim import run as install_claim_run
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


def test_install_claim_fixture_is_error():
    trace = load_generic(FIXTURES / "install_claim.jsonl")
    findings = install_claim_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "install_claim"
    assert findings[0].severity == "error"
    assert findings[0].title == "claimed a package install with no install command"


def test_install_claim_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "install_claim_ok.jsonl")
    assert install_claim_run(trace) == []


def test_claim_phrases_are_error():
    for text in (
        "I installed the package.",
        "pip install succeeded.",
        "npm install is done.",
        "The package is installed.",
    ):
        findings = install_claim_run(_trace("look at the repo", text))
        assert findings, text
        assert findings[0].detector == "install_claim"
        assert findings[0].severity == "error"
        assert findings[0].title == "claimed a package install with no install command"


def test_ask_phrases_are_warn():
    for text in (
        "please install requests",
        "pip install flask",
        "npm install",
    ):
        findings = install_claim_run(_trace(text, "Working on it."))
        assert findings, text
        assert findings[0].detector == "install_claim"
        assert findings[0].severity == "warn"
        assert findings[0].title == (
            "a package install was requested; no install command in the trace"
        )


def test_future_tense_silent_if_not_asked():
    assert install_claim_run(_trace("look at the repo", "I will install the package.")) == []
    assert install_claim_run(_trace("look at the repo", "I'll install the package.")) == []


def test_failed_pip_install_with_claim_is_error():
    tool = _cmd("pip install requests", outcome="error", result="exit: 1\nERROR")
    findings = install_claim_run(
        _trace("please install requests", "I installed the package.", [tool])
    )
    assert len(findings) == 1
    assert findings[0].detector == "install_claim"
    assert findings[0].severity == "error"


def test_failed_install_with_ask_only_is_warn():
    tool = _cmd("npm install", outcome="error", result="exit: 1\nnpm ERR!")
    findings = install_claim_run(_trace("please npm install", "Working on it.", [tool]))
    assert len(findings) == 1
    assert findings[0].severity == "warn"


def test_pytest_is_not_an_install():
    findings = install_claim_run(
        _trace("please install requests", "I installed the package.", [_cmd("pytest")])
    )
    assert len(findings) == 1
    assert findings[0].detector == "install_claim"
    assert findings[0].severity == "error"


def test_yarn_without_add_is_not_an_install():
    findings = install_claim_run(
        _trace("please install requests", "I installed the package.", [_cmd("yarn")])
    )
    assert findings
    assert findings[0].severity == "error"


def test_no_ask_no_claim_silent():
    assert install_claim_run(_trace("how does this repo work?", "Here is the layout.")) == []


def test_successful_install_commands_are_silent():
    for cmd in (
        "pip install flask",
        "pip3 install flask",
        "python -m pip install flask",
        "npm install",
        "pnpm install",
        "pnpm add lodash",
        "yarn add lodash",
        "poetry add flask",
        "go get example.com/mod",
        "cargo add serde",
    ):
        assert (
            install_claim_run(
                _trace("please install requests", "I installed the package.", [_cmd(cmd)])
            )
            == []
        ), cmd


def test_cmd_array_pip_install_is_silent():
    tool = ToolCall(
        id="c1",
        name="shell",
        arguments=json.dumps({"cmd": ["pip", "install", "requests"]}),
        result="Successfully installed requests",
        outcome="success",
    )
    assert (
        install_claim_run(_trace("please install requests", "I installed the package.", [tool]))
        == []
    )


def test_claim_takes_priority_over_ask():
    findings = install_claim_run(_trace("please install requests", "I installed the package."))
    assert len(findings) == 1
    assert findings[0].severity == "error"
