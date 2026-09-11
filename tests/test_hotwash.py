import sys
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


def test_tests_claim_fires_when_pytest_failed():
    trace = load(FIXTURES / "tool_fail.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "tests_claim" in dets


def test_write_case_and_eval_roundtrip(tmp_path):
    dest = tmp_path / "suite" / "tool_fail"
    code = main([str(FIXTURES / "tool_fail.jsonl"), "--write-case", str(dest)])
    assert code == 1  # source session is dirty
    assert dest.with_suffix(".jsonl").exists()
    assert Path(str(dest) + ".expect.json").exists()
    # clean case in the same suite
    dest2 = tmp_path / "suite" / "clean"
    assert main([str(FIXTURES / "clean.jsonl"), "--write-case", str(dest2)]) == 0
    assert main(["--eval", str(tmp_path / "suite")]) == 0


ROOT = Path(__file__).resolve().parents[1]


def test_public_case_corpus():
    assert main(["--eval", str(ROOT / "cases")]) == 0


def test_push_claim_without_git_push():
    trace = load(FIXTURES / "push_fail.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "push_claim" in dets
    assert rank(run_all(trace, ["push_claim"]))[0] == "FINDINGS"


def test_stdin_and_eval_json(monkeypatch):
    import io
    import json

    payload = (FIXTURES / "clean.jsonl").read_text()
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert main(["-"]) == 0
    # json eval of the public corpus
    import hotwash.cli as cli

    old = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    try:
        code = main(["--eval", str(ROOT / "cases"), "--format", "json"])
    finally:
        sys.stdout = old
    assert code == 0
    rows = json.loads(buf.getvalue())
    assert {r["name"] for r in rows} >= {"clean", "tool_fail"}


def test_verify_http_404_is_not_live():
    trace = load(FIXTURES / "http_fail.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "verify_http" in dets
    assert "ship_claim" not in dets
    assert rank(run_all(trace, ["verify_http"]))[0] == "FINDINGS"


def test_commit_claim_without_git_commit():
    trace = load(FIXTURES / "commit_fail.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "commit_claim" in dets
    assert rank(run_all(trace, ["commit_claim"]))[0] == "FINDINGS"


def test_codex_ingest_apply_patch_and_exit_code():
    trace = load(FIXTURES / "codex_mini.jsonl")
    assert trace.session_id == "codex-mini"
    assert [t.name for t in trace.tools] == ["apply_patch", "shell"]
    assert trace.tools[1].outcome == "error"
    users = [m.content for m in trace.messages if m.role == "user"]
    assert users == ["Fix the README typo and run the tests."]
    dets = {f.detector for f in run_all(trace)}
    assert "emdash" in dets
    assert "tests_claim" in dets
    assert "tool_error" in dets


def test_shell_cmd_array_counts_as_git_push():
    trace = load(FIXTURES / "cmd_array_push.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "push_claim" not in dets


def test_strict_turns_warnings_into_errors():
    # todos is warn-only on the dirty grok fixture
    assert main([str(FIXTURES / "grok_mini"), "--detectors", "todos"]) == 0
    assert main([str(FIXTURES / "grok_mini"), "--detectors", "todos", "--strict"]) == 1


def test_secret_write_flags_live_shaped_key():
    trace = load(FIXTURES / "secret_write.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "secret_write" in dets
    assert rank(run_all(trace, ["secret_write"]))[0] == "FINDINGS"


def test_write_case_secret_roundtrip_still_flags(tmp_path):
    dest = tmp_path / "suite" / "secret_write"
    assert main([str(FIXTURES / "secret_write.jsonl"), "--write-case", str(dest)]) == 1
    text = dest.with_suffix(".jsonl").read_text()
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in text
    assert main(["--eval", str(tmp_path / "suite")]) == 0


def test_dump_trace_redacts_secret(tmp_path):
    import json

    out = tmp_path / "trace.json"
    assert main([str(FIXTURES / "secret_write.jsonl"), "--dump-trace", "-o", str(out)]) == 0
    blob = out.read_text()
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in blob
    data = json.loads(blob)
    assert data["tools"]


def test_codex_session_discovery(tmp_path, monkeypatch):
    from hotwash.discover import all_sessions, codex_sessions, latest_session

    root = tmp_path / "codex" / "sessions" / "2026" / "09" / "11"
    root.mkdir(parents=True)
    rollout = root / "rollout-2026-09-11T00-00-00-codex-mini.jsonl"
    rollout.write_text((FIXTURES / "codex_mini.jsonl").read_text())
    found = codex_sessions(tmp_path / "codex" / "sessions")
    assert found == [rollout]

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr("hotwash.discover.grok_sessions", lambda: [])
    monkeypatch.setattr("hotwash.discover.claude_sessions", lambda: [])
    monkeypatch.setattr("hotwash.discover.cursor_sessions", lambda: [])
    rows = all_sessions()
    assert rows[0][0] == "codex"
    assert latest_session() == rollout


def test_stale_verify_curl_before_write():
    trace = load(FIXTURES / "stale_verify.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "stale_verify" in dets
    assert "ship_claim" not in dets
    assert rank(run_all(trace, ["stale_verify"]))[0] == "FINDINGS"


def test_stale_verify_curl_after_push_is_clean():
    dets = {f.detector for f in run_all(load(FIXTURES / "clean.jsonl"))}
    assert "stale_verify" not in dets


def test_pr_claim_without_gh_pr_create():
    trace = load(FIXTURES / "pr_fail.jsonl")
    dets = {f.detector for f in run_all(trace)}
    assert "pr_claim" in dets
    assert rank(run_all(trace, ["pr_claim"]))[0] == "FINDINGS"


def test_pr_claim_gh_pr_create_is_clean():
    dets = {f.detector for f in run_all(load(FIXTURES / "pr_ok.jsonl"))}
    assert "pr_claim" not in dets


def test_quiet_prints_rank_and_lines_only(capsys):
    code = main([str(FIXTURES / "pr_fail.jsonl"), "--quiet"])
    assert code == 1
    out = capsys.readouterr().out
    assert out.startswith("rank FINDINGS")
    assert "pr_claim" in out
    assert "HOTWASH" not in out
    assert "after-action review" not in out


def test_write_claim_is_registered():
    from hotwash.detectors import REGISTRY

    assert "write_claim" in REGISTRY
    dets = {f.detector for f in run_all(load(FIXTURES / "write_claim.jsonl"))}
    assert "write_claim" in dets


def test_cli_coverage_green_on_public_cases():
    assert main(["--coverage", str(ROOT / "cases")]) == 0


def test_list_rank_includes_path_and_rank(tmp_path, capsys, monkeypatch):
    dest = tmp_path / "clean.jsonl"
    dest.write_text((FIXTURES / "clean.jsonl").read_text())
    monkeypatch.setattr("hotwash.cli.all_sessions", lambda: [("generic", dest)])
    assert main(["--list", "--rank"]) == 0
    out = capsys.readouterr().out
    assert "CLEAN" in out
    assert "generic" in out
    assert str(dest) in out
