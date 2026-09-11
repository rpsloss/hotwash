import json
from pathlib import Path

from hotwash.detectors.stale_verify import run as stale_verify_run
from hotwash.ingest.generic import load_generic
from hotwash.model import Message, ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"


def _curl(cid: str = "c1", status: int = 200) -> ToolCall:
    return ToolCall(
        id=cid,
        name="run_terminal_command",
        arguments=json.dumps({"command": "curl -sI https://example.com"}),
        result=f"HTTP/2 {status}\ncontent-type: text/html",
        outcome="success",
    )


def _write(cid: str = "c2") -> ToolCall:
    return ToolCall(
        id=cid,
        name="write",
        arguments=json.dumps({"path": "a.py", "content": "x = 1\n"}),
        result="wrote a.py",
        outcome="success",
    )


def _commit(cid: str = "c3", ok: bool = True) -> ToolCall:
    return ToolCall(
        id=cid,
        name="run_terminal_command",
        arguments=json.dumps({"command": "git commit -m x"}),
        result="[main abc] x" if ok else "exit: 1\nnothing to commit",
        outcome="success" if ok else "error",
    )


def _trace(tools: list[ToolCall], *, asked: bool = True, claimed: bool = True) -> Trace:
    messages: list[Message] = []
    if asked:
        messages.append(Message(role="user", content="please deploy this to production"))
    else:
        messages.append(Message(role="user", content="update the copy"))
    if claimed:
        messages.append(Message(role="assistant", content="It's live. You can check now."))
    return Trace(source="mem", messages=messages, tools=tools)


def test_stale_verify_fixture_is_error():
    trace = load_generic(FIXTURES / "stale_verify.jsonl")
    findings = stale_verify_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "stale_verify"
    assert findings[0].severity == "error"


def test_stale_verify_ok_fixture_is_silent():
    trace = load_generic(FIXTURES / "stale_verify_ok.jsonl")
    assert stale_verify_run(trace) == []


def test_ask_without_claim_is_warn():
    findings = stale_verify_run(_trace([_curl(), _write()], claimed=False))
    assert len(findings) == 1
    assert findings[0].detector == "stale_verify"
    assert findings[0].severity == "warn"


def test_git_commit_after_probe_is_stale():
    findings = stale_verify_run(_trace([_curl(), _commit()]))
    assert findings
    assert findings[0].detector == "stale_verify"
    assert findings[0].severity == "error"


def test_failed_commit_after_probe_is_not_stale():
    assert stale_verify_run(_trace([_curl(), _commit(ok=False)])) == []


def test_no_ship_ask_or_claim_is_silent():
    assert stale_verify_run(_trace([_curl(), _write()], asked=False, claimed=False)) == []


def test_no_2xx_probe_is_silent():
    assert stale_verify_run(_trace([_curl(status=404), _write()])) == []


def test_later_2xx_after_write_is_silent():
    assert stale_verify_run(_trace([_curl("c1"), _write("c2"), _curl("c3")])) == []


def test_search_replace_after_probe_is_stale():
    replace = ToolCall(
        id="c2",
        name="search_replace",
        arguments=json.dumps(
            {"file_path": "a.py", "old_string": "x", "new_string": "y"}
        ),
        result="updated a.py",
        outcome="success",
    )
    findings = stale_verify_run(_trace([_curl(), replace]))
    assert findings
    assert findings[0].detector == "stale_verify"
