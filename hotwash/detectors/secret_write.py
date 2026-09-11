from __future__ import annotations

import re

from hotwash.detectors.util import is_write_tool, write_path, written_text
from hotwash.model import Finding, Trace
from hotwash.redact import REDACTED_TOKEN, redact

SECRET_NAMES = (
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "STRIPE_SECRET_KEY",
    "PRIVATE_KEY",
)

_NAME = "|".join(SECRET_NAMES)

# JSON / env / export assignment. Docs without = or : do not match.
# Unquoted values must be non-empty and cannot contain '=' (next key).
ASSIGN = re.compile(
    r"(?m)(?:^|[\s,{])(?:export\s+)?\[?[\"']?(?:"
    + _NAME
    + r")[\"']?\]?\s*[=:]\s*"
    r"(?:'(?P<sval>[^'\n]*)'|\"(?P<dval>[^\"\n]*)\"|(?P<uval>[^\s,;}#\n=]+))?"
)

TOKEN = re.compile(
    r"(?:(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{20,}"
    r"|(?<![A-Za-z0-9_])sk_live_[A-Za-z0-9]{16,}"
    r"|(?<![A-Za-z0-9_])ghp_[A-Za-z0-9]{20,}"
    r"|(?<![A-Za-z0-9_])xai-[A-Za-z0-9_-]{20,}"
    r"|(?<![A-Za-z0-9_])AKIA[0-9A-Z]{16}(?![A-Za-z0-9]))"
)

PEM = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")

PLACEHOLDER = re.compile(
    r"(?i)^(?:"
    r"your[-_\s]?[\w.-]*here"
    r"|your[-_]?(?:api[-_]?key|secret|token|key|password)"
    r"|<[^>]*>"
    r"|\$\{[^}]*\}"
    r"|\$[A-Z_][A-Z0-9_]*"
    r"|x{3,}"
    r"|\*{2,}"
    r"|\.{3,}"
    r"|placeholder"
    r"|redacted"
    r"|changeme"
    r"|change[-_\s]?me"
    r"|dummy"
    r"|example"
    r"|insert\b.*"
    r"|replace\b.*"
    r"|paste\b.*"
    r"|todo"
    r"|none"
    r"|null"
    r"|undefined"
    r"|n/?a"
    r"|secret"
    r"|password"
    r"|token"
    r"|key"
    r"|test"
    r"|required"
    r")$"
)


def run(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    for tool in trace.tools:
        if not is_write_tool(tool):
            continue
        path = write_path(tool)
        if _example_fixture(path):
            continue
        blob = written_text(tool)
        if not _secret_in(blob):
            continue
        findings.append(
            Finding(
                detector="secret_write",
                severity="error",
                title=f"secret written into {path or tool.name}",
                detail="The agent wrote an API key, token, or private key into a file. Put secrets in the environment or a secret store, not in the repo.",
                evidence=(path or tool.name) + "\n" + redact(_snip(blob)),
            )
        )
    return findings


def _example_fixture(path: str) -> bool:
    """Skip tests/fixtures files whose names contain 'example'."""
    if not path:
        return False
    norm = path.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    if "example" not in base.lower():
        return False
    lowered = "/" + norm.lower().lstrip("/")
    return "/tests/fixtures/" in lowered


def _secret_in(text: str) -> bool:
    if not text:
        return False
    if REDACTED_TOKEN in text or "[REDACTED]" in text:
        return True
    if PEM.search(text):
        return True
    for m in TOKEN.finditer(text):
        if not _token_placeholder(m.group(0)):
            return True
    for m in ASSIGN.finditer(text):
        val = m.group("sval")
        if val is None:
            val = m.group("dval")
        if val is None:
            val = m.group("uval")
        if _assigned_secret((val or "").strip()):
            return True
    return False


def _assigned_secret(val: str) -> bool:
    if not val or val in SECRET_NAMES or _is_placeholder(val):
        return False
    tok = TOKEN.search(val)
    if tok and not _token_placeholder(tok.group(0)):
        return True
    if PEM.search(val):
        return True
    if _looks_code(val) or _looks_path(val):
        return False
    return len(val) >= 12


def _is_placeholder(val: str) -> bool:
    if PLACEHOLDER.match(val):
        return True
    low = val.lower()
    for needle in (
        "your-key",
        "your_key",
        "yourkey",
        "placeholder",
        "example",
        "changeme",
        "redacted",
        "insert-",
        "replace-",
    ):
        if needle in low:
            return True
    return False


def _token_placeholder(tok: str) -> bool:
    if re.search(r"example|placeholder|your.?key|changeme|redacted", tok, re.I):
        return True
    body = re.sub(r"^(?:sk-proj-|sk_live_|sk-|ghp_|xai-|AKIA)", "", tok)
    compact = re.sub(r"[-_]", "", body)
    return bool(compact) and len(set(compact.lower())) <= 2


def _looks_code(val: str) -> bool:
    if "(" in val or "[" in val:
        return True
    if val.startswith(("os.", "process.", "env.", "self.", "config.", "settings.")):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+", val):
        return True
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", val) and len(val) < 20)


def _looks_path(val: str) -> bool:
    if val.startswith(("/", "./", "../", "~")):
        return True
    return bool(re.search(r"\.(pem|key|env|json)$", val, re.I))


def _snip(text: str, n: int = 240) -> str:
    return " ".join(text.split())[:n]
