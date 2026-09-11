import json
from pathlib import Path

from hotwash.case import REDACTED, trace_to_jsonl, write_case
from hotwash.redact import REDACTED_TOKEN
from hotwash.model import Message, ToolCall, Trace

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_PAT = "ghp_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
STRIPE_KEY = "sk" + "_live_" + "51AaBbCcDdEeFfGgHhIiJjKk"
XAI_KEY = "xai-0123456789abcdefghijABCDEFGH"
OPENAI_KEY = "sk-abcdefghijklmnopqrstuvwxyz012345"
PEM_BODY = "MIIEowIBAAKFAKESECRET_q1r2s3t4u5v6w7x8y9z0"
PEM = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    f"{PEM_BODY}\n"
    "-----END RSA PRIVATE KEY-----"
)
ENV_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
QUOTED_SECRET = "quoted-plain-secret-value"
RAW_SECRETS = (
    AWS_KEY,
    GITHUB_PAT,
    STRIPE_KEY,
    XAI_KEY,
    OPENAI_KEY,
    PEM_BODY,
    ENV_SECRET,
    QUOTED_SECRET,
)


def _trace(*, content: str = "", arguments: str = "", result: str = "", name: str = "write") -> Trace:
    call = ToolCall(
        id="c1",
        name=name,
        arguments=arguments,
        result=result,
        outcome="success" if (arguments or result) else "",
    )
    msg = Message(
        role="assistant",
        content=content,
        tool_calls=[call] if (arguments or result) else [],
    )
    tools = [call] if msg.tool_calls else []
    return Trace(source="memory", session_id="redact", messages=[msg], tools=tools)


def _assert_no_raw_secrets(blob: str) -> None:
    for secret in RAW_SECRETS:
        assert secret not in blob
    assert REDACTED in blob or REDACTED_TOKEN in blob


def test_trace_to_jsonl_redacts_tokens():
    content = " ".join([AWS_KEY, GITHUB_PAT, STRIPE_KEY, XAI_KEY, OPENAI_KEY])
    blob = trace_to_jsonl(_trace(content=content))
    _assert_no_raw_secrets(blob)


def test_trace_to_jsonl_redacts_pem_private_key():
    blob = trace_to_jsonl(_trace(content=PEM, result=PEM))
    _assert_no_raw_secrets(blob)
    assert "BEGIN RSA PRIVATE KEY" in blob
    assert "END RSA PRIVATE KEY" in blob


def test_trace_to_jsonl_redacts_env_assignments():
    assignments = "\n".join(
        [
            f"OPENAI_API_KEY={OPENAI_KEY}",
            f"XAI_API_KEY={XAI_KEY}",
            f"ANTHROPIC_API_KEY={ENV_SECRET}",
            f"AWS_SECRET_ACCESS_KEY={ENV_SECRET}",
            f'GITHUB_TOKEN="{QUOTED_SECRET}"',
            f"GH_TOKEN='{QUOTED_SECRET}'",
        ]
    )
    arguments = json.dumps({"path": ".env", "content": assignments})
    blob = trace_to_jsonl(_trace(arguments=arguments, name="write"))
    _assert_no_raw_secrets(blob)
    assert "OPENAI_API_KEY=" in blob
    assert "XAI_API_KEY=" in blob
    assert "ANTHROPIC_API_KEY=" in blob
    assert "AWS_SECRET_ACCESS_KEY=" in blob
    assert "GITHUB_TOKEN=" in blob
    assert "GH_TOKEN=" in blob


def test_trace_to_jsonl_keeps_path_and_tool_name():
    arguments = json.dumps({"path": "secrets/prod.env", "content": f"OPENAI_API_KEY={OPENAI_KEY}"})
    blob = trace_to_jsonl(_trace(arguments=arguments, name="write"))
    _assert_no_raw_secrets(blob)
    assert "write" in blob
    assert "secrets/prod.env" in blob
    assert "OPENAI_API_KEY=" in blob


def test_redact_does_not_mutate_trace():
    arguments = json.dumps({"path": ".env", "content": f"GH_TOKEN={ENV_SECRET}"})
    trace = _trace(content=GITHUB_PAT, arguments=arguments, result=PEM)
    _ = trace_to_jsonl(trace)
    assert trace.messages[0].content == GITHUB_PAT
    assert ENV_SECRET in trace.tools[0].arguments
    assert PEM_BODY in trace.tools[0].result


def test_write_case_redacts_secret(tmp_path: Path):
    arguments = json.dumps({"path": ".env", "content": f"OPENAI_API_KEY={OPENAI_KEY}"})
    trace = _trace(content=f"wrote {GITHUB_PAT}", arguments=arguments, result=AWS_KEY)
    jsonl, _expect = write_case(trace, [], tmp_path / "secret")
    text = jsonl.read_text()
    _assert_no_raw_secrets(text)
    assert "write" in text
    assert ".env" in text
