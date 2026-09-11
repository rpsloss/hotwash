from pathlib import Path

from hotwash.summarize import session_preview

FIXTURES = Path(__file__).parent / "fixtures"


def test_tool_fail_preview_is_findings():
    path = FIXTURES / "tool_fail.jsonl"
    preview = session_preview(path)
    assert preview["kind"] == "generic"
    assert Path(preview["path"]).name == "tool_fail.jsonl"
    assert preview["rank"] == "FINDINGS"
    assert "tests_claim" in preview["detectors"]
    assert "tool_error" in preview["detectors"]
    assert preview["user_turns"] == 1
    assert preview["tools"] == 1
    assert preview["prompt"] == "run the tests and tell me when they pass"
    assert len(preview["prompt"]) <= 80


def test_clean_preview_is_clean():
    path = FIXTURES / "clean.jsonl"
    preview = session_preview(path)
    assert preview["kind"] == "generic"
    assert preview["rank"] == "CLEAN"
    assert preview["detectors"] == []
    assert preview["user_turns"] == 1
    assert preview["tools"] == 5
    assert preview["prompt"] == (
        "Update the about page, push to git, and deploy to Vercel. Confirm production."
    )
    assert len(preview["prompt"]) <= 80


def test_load_error_is_rank_error(tmp_path):
    missing = tmp_path / "no-such-session.jsonl"
    preview = session_preview(missing)
    assert preview["rank"] == "ERROR"
    assert preview["prompt"] == ""
    assert preview["detectors"] == []
    assert preview["user_turns"] == 0
    assert preview["tools"] == 0
    assert Path(preview["path"]).name == "no-such-session.jsonl"
