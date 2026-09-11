from pathlib import Path

from hotwash.discover import all_sessions, cursor_sessions
from hotwash.ingest import load, load_cursor
from hotwash.ingest.sniff import sniff_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_sniff_cursor_jsonl():
    assert sniff_file(FIXTURES / "cursor_mini.jsonl") == "cursor"


def test_sniff_prefers_claude_type_and_message_role():
    assert sniff_file(FIXTURES / "claude_mini.jsonl") == "claude"


def test_sniff_codex_and_generic_unchanged():
    assert sniff_file(FIXTURES / "codex_mini.jsonl") == "codex"
    assert sniff_file(FIXTURES / "clean.jsonl") == "generic"


def test_sniff_role_without_message_content_list_is_not_cursor(tmp_path):
    p = tmp_path / "plain.jsonl"
    p.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
    assert sniff_file(p) == "generic"


def test_load_cursor_parses_text_and_tools():
    trace = load(FIXTURES / "cursor_mini.jsonl")
    assert trace.session_id == "cursor_mini"
    users = [m.content for m in trace.messages if m.role == "user"]
    assert users == ["list files in demo_app"]
    assert [t.name for t in trace.tools] == ["Read", "Shell"]
    assert trace.tools[0].id == "c1"
    assert '"path": "demo_app/README.md"' in trace.tools[0].arguments
    assert "toy project" in trace.tools[0].result
    assert trace.tools[1].outcome == "error"
    assert "FAILED tests/test_demo.py" in trace.tools[1].result
    assistants = [m.content for m in trace.messages if m.role == "assistant"]
    assert assistants[0] == "Reading README.md"
    assert assistants[1] == "README is a toy project. Tests failed."
    assert [c.id for c in trace.messages[1].tool_calls] == ["c1", "c2"]


def test_load_cursor_direct_matches_sniff_route():
    via_sniff = load(FIXTURES / "cursor_mini.jsonl")
    direct = load_cursor(FIXTURES / "cursor_mini.jsonl")
    assert [m.role for m in via_sniff.messages] == [m.role for m in direct.messages]
    assert [t.name for t in via_sniff.tools] == [t.name for t in direct.tools]


def test_cursor_sessions_under_agent_transcripts(tmp_path):
    dest = tmp_path / "empty-window" / "agent-transcripts" / "sess" / "sess.jsonl"
    dest.parent.mkdir(parents=True)
    dest.write_text("{}\n", encoding="utf-8")
    skipped = tmp_path / "empty-window" / "other.jsonl"
    skipped.write_text("{}\n", encoding="utf-8")
    found = cursor_sessions(tmp_path)
    assert found == [dest]


def test_all_sessions_includes_cursor(tmp_path, monkeypatch):
    dest = tmp_path / "agent-transcripts" / "sess.jsonl"
    dest.parent.mkdir(parents=True)
    dest.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("hotwash.discover.grok_sessions", lambda: [])
    monkeypatch.setattr("hotwash.discover.claude_sessions", lambda: [])
    monkeypatch.setattr("hotwash.discover.codex_sessions", lambda: [])
    monkeypatch.setattr("hotwash.discover.cursor_sessions", lambda: [dest])
    rows = all_sessions()
    assert rows == [("cursor", dest)]
