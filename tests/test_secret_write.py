import json
from pathlib import Path

from hotwash.detectors.secret_write import run as secret_write_run
from hotwash.ingest.generic import load_generic
from hotwash.model import ToolCall, Trace

FIXTURES = Path(__file__).parent / "fixtures"

FAKE_OPENAI = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD"
FAKE_GHP = "ghp_abcdefghijklmnopqrstuvwxyz012345"
FAKE_XAI = "xai-abcdefghijklmnopqrstuvwxyz012345"
FAKE_AKIA = "AKIAIOSFODNN7ABCDEFG"


def _write(path: str, content: str, name: str = "write") -> Trace:
    args = json.dumps({"path": path, "content": content, "file_path": path})
    tool = ToolCall(id="c1", name=name, arguments=args)
    return Trace(source="mem", tools=[tool])


def _replace(path: str, old: str, new: str) -> Trace:
    args = json.dumps({"file_path": path, "old_string": old, "new_string": new})
    tool = ToolCall(id="c1", name="search_replace", arguments=args)
    return Trace(source="mem", tools=[tool])


def _patch(path: str, body: str) -> Trace:
    patch = f"*** Begin Patch\n*** Update File: {path}\n{body}\n*** End Patch"
    tool = ToolCall(id="c1", name="apply_patch", arguments=patch)
    return Trace(source="mem", tools=[tool])


def test_secret_write_dirty_fixture_is_error():
    trace = load_generic(FIXTURES / "secret_write.jsonl")
    findings = secret_write_run(trace)
    assert findings
    assert all(f.detector == "secret_write" for f in findings)
    assert all(f.severity == "error" for f in findings)
    assert any(".env" in f.title for f in findings)


def test_secret_write_clean_fixture_is_silent():
    trace = load_generic(FIXTURES / "secret_write_clean.jsonl")
    assert secret_write_run(trace) == []


def test_docs_without_a_value_do_not_fire():
    trace = _write(
        "README.md",
        "Set OPENAI_API_KEY in env. Also set GITHUB_TOKEN, GH_TOKEN, and STRIPE_SECRET_KEY.",
    )
    assert secret_write_run(trace) == []


def test_env_example_placeholders_do_not_fire():
    trace = _write(
        ".env.example",
        "OPENAI_API_KEY=\nGITHUB_TOKEN=your-key-here\nXAI_API_KEY=<YOUR_KEY>\n",
    )
    assert secret_write_run(trace) == []


def test_example_fixture_path_does_not_fire():
    trace = _write(
        "tests/fixtures/keys_example.json",
        json.dumps({"OPENAI_API_KEY": FAKE_OPENAI, "GITHUB_TOKEN": FAKE_GHP}),
    )
    assert secret_write_run(trace) == []


def test_old_string_secret_is_not_a_finding():
    trace = _replace(
        "app.py",
        f"OPENAI_API_KEY={FAKE_OPENAI}",
        'OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]',
    )
    assert secret_write_run(trace) == []


def test_deleted_patch_line_is_not_a_finding():
    trace = _patch(
        ".env",
        f"@@\n-OPENAI_API_KEY={FAKE_OPENAI}\n+OPENAI_API_KEY=\n",
    )
    assert secret_write_run(trace) == []


def test_json_assignment_fires():
    trace = _write(
        "config.json",
        json.dumps({"OPENAI_API_KEY": FAKE_OPENAI, "debug": True}),
    )
    findings = secret_write_run(trace)
    assert len(findings) == 1
    assert findings[0].detector == "secret_write"
    assert findings[0].severity == "error"
    assert "config.json" in findings[0].title


def test_named_env_keys_fire():
    for name, value in (
        ("XAI_API_KEY", FAKE_XAI),
        ("ANTHROPIC_API_KEY", FAKE_OPENAI),
        ("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYABCDEF"),
        ("GITHUB_TOKEN", FAKE_GHP),
        ("GH_TOKEN", FAKE_GHP),
        ("STRIPE_SECRET_KEY", "sk" + "_live_" + "abcdefghijklmnopqrstuvwxyz"),
        ("PRIVATE_KEY", "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC"),
    ):
        findings = secret_write_run(_write(".env", f"{name}={value}\n"))
        assert findings, name
        assert findings[0].detector == "secret_write"


def test_token_values_without_name_fire():
    samples = (
        ("cfg.txt", FAKE_OPENAI),
        ("cfg.txt", FAKE_GHP),
        ("cfg.txt", FAKE_XAI),
        ("cfg.txt", FAKE_AKIA),
        ("cfg.txt", "sk" + "_live_" + "abcdefghijklmnopqrstuvwxyz0123"),
    )
    for path, blob in samples:
        findings = secret_write_run(_write(path, f"token = {blob}\n"))
        assert findings, blob


def test_pem_headers_fire():
    for header in (
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
    ):
        findings = secret_write_run(_write("id_rsa", header + "\nMIIE\n"))
        assert findings, header
        assert findings[0].severity == "error"


def test_apply_patch_plus_line_fires():
    trace = _patch(
        ".env",
        f"@@\n-FOO=bar\n+OPENAI_API_KEY={FAKE_OPENAI}\n",
    )
    findings = secret_write_run(trace)
    assert findings
    assert ".env" in findings[0].title


def test_code_that_reads_env_does_not_fire():
    trace = _write(
        "app.py",
        'OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]\n'
        "key = os.getenv('GITHUB_TOKEN')\n",
    )
    assert secret_write_run(trace) == []


def test_non_write_tool_is_ignored():
    args = json.dumps({"command": f"echo OPENAI_API_KEY={FAKE_OPENAI}"})
    tool = ToolCall(id="c1", name="run_terminal_command", arguments=args)
    assert secret_write_run(Trace(source="mem", tools=[tool])) == []
