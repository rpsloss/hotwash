from pathlib import Path

from hotwash.cli import main
from hotwash.detectors import run_all
from hotwash.ingest import load
from hotwash.report import rank

FIXTURES = Path(__file__).parent / "fixtures"


def test_dirty_grok_session_trips_core_detectors():
    trace = load(FIXTURES / "grok_mini")
    assert trace.session_id == "grok_mini"
    assert len(trace.tools) == 3
    findings = run_all(trace)
    dets = {f.detector for f in findings}
    assert "emdash" in dets
    assert "git_identity" in dets
    assert "ship_claim" in dets
    assert "todos" in dets
    assert rank(findings)[0] == "FINDINGS"


def test_clean_generic_trace_is_clean():
    trace = load(FIXTURES / "clean.jsonl")
    findings = run_all(trace)
    assert findings == []
    assert rank(findings)[0] == "CLEAN"


def test_cli_exits_nonzero_on_errors(tmp_path):
    out = tmp_path / "aar.md"
    code = main([str(FIXTURES / "grok_mini"), "--format", "md", "-o", str(out)])
    assert code == 1
    text = out.read_text()
    assert "Hotwash" in text
    assert "em-dash" in text or "emdash" in text


def test_cli_clean_is_zero():
    code = main([str(FIXTURES / "clean.jsonl")])
    assert code == 0


def test_removing_an_emdash_is_not_a_finding():
    from hotwash.ingest.generic import load_generic
    from hotwash.detectors.emdash import run as emdash_run

    trace = load_generic(FIXTURES / "scrub_emdash.jsonl")
    assert emdash_run(trace) == []


def test_git_log_of_old_mac_lan_is_not_a_finding():
    from hotwash.ingest.generic import load_generic
    from hotwash.detectors.git_identity import run as git_run

    trace = load_generic(FIXTURES / "git_log.jsonl")
    assert git_run(trace) == []


def test_grok_ingest_strips_user_query_wrapper():
    trace = load(FIXTURES / "grok_wrapped")
    users = [m.content for m in trace.messages if m.role == "user"]
    assert users == ["please deploy this to production"]
    findings = run_all(trace)
    assert any(f.detector == "ship_claim" for f in findings)


def test_cli_list_and_unknown_detector(tmp_path):
    from hotwash.discover import grok_sessions, latest_grok_session

    root = tmp_path / "sessions" / "ws" / "abc"
    root.mkdir(parents=True)
    (root / "chat_history.jsonl").write_text("{}\n")
    found = grok_sessions(tmp_path / "sessions")
    assert found == [root]
    assert latest_grok_session(tmp_path / "sessions") == root

    code = main([str(FIXTURES / "clean.jsonl"), "--detectors", "not_a_detector"])
    assert code == 2


def test_cli_detectors_filter():
    code = main([str(FIXTURES / "grok_mini"), "--detectors", "todos"])
    # todos is warn-only on the dirty fixture, so exit 0
    assert code == 0


def test_tool_error_after_failed_test_and_success_claim():
    trace = load(FIXTURES / "tool_fail.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "tool_error" in dets
    assert rank(run_all(trace, ["tool_error"]))[0] == "FINDINGS"


def test_claude_ingest_and_failed_bash():
    trace = load(FIXTURES / "claude_mini.jsonl")
    assert trace.session_id == "claude-mini"
    assert [t.name for t in trace.tools] == ["Bash"]
    assert trace.tools[0].outcome == "error"
    users = [m.content for m in trace.messages if m.role == "user"]
    assert users == ["deploy this to production"]
    dets = {f.detector for f in run_all(trace)}
    assert "tool_error" in dets
    assert "ship_claim" in dets


def test_dump_trace_cli(tmp_path):
    out = tmp_path / "trace.json"
    code = main([str(FIXTURES / "clean.jsonl"), "--dump-trace", "-o", str(out)])
    assert code == 0
    data = __import__("json").loads(out.read_text())
    assert "messages" in data
    assert "tools" in data
