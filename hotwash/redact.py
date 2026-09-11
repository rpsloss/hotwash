from __future__ import annotations

import json
import re
from typing import Any

REDACTED = "[REDACTED]"
REDACTED_TOKEN = "[REDACTED-TOKEN]"

_PEM = re.compile(
    r"(-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----)(.*?)(-----END [A-Z0-9 ]*PRIVATE KEY-----)",
    re.DOTALL,
)
_PEM_DANGLING = re.compile(
    r"(-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----)(?!.*-----END [A-Z0-9 ]*PRIVATE KEY-----).*",
    re.DOTALL,
)
_ENV_KEYS = (
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)
_ENV = re.compile(
    r"\b("
    + "|".join(_ENV_KEYS)
    + r")\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|(\S+))"
)
_TOKENS = re.compile(
    r"\bAKIA[0-9A-Z]{16}\b"
    r"|\bghp_[A-Za-z0-9]{36,}\b"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
    r"|\bsk_live_[A-Za-z0-9]{16,}\b"
    r"|\bxai-[A-Za-z0-9_-]{24,}"
    r"|\bsk-[A-Za-z0-9_-]{24,}"
)
def _env_value(match: re.Match) -> str:
    return match.group(2) or match.group(3) or match.group(4) or ""


def _env_repl(match: re.Match) -> str:
    key = match.group(1)
    value = _env_value(match)
    if not _should_redact_value(value):
        return match.group(0)
    standin = REDACTED_TOKEN if secret_kinds(value) else REDACTED
    if match.group(2) is not None:
        return f"{key}='{standin}'"
    if match.group(3) is not None:
        return f'{key}="{standin}"'
    return f"{key}={standin}"


def _should_redact_value(value: str) -> bool:
    if not value or value in {REDACTED, REDACTED_TOKEN}:
        return False
    if secret_kinds(value):
        return True
    # Long env values on known key names are likely secrets even without a prefix.
    if len(value) >= 24:
        return True
    return False


def _token_repl(match: re.Match) -> str:
    return REDACTED_TOKEN


def redact_text(text: str) -> str:
    """Replace secret values. Leaves key names, paths, tool names, placeholders."""
    if not text:
        return text
    text = _PEM.sub(lambda m: f"{m.group(1)}\n{REDACTED_TOKEN}\n{m.group(3)}", text)
    text = _PEM_DANGLING.sub(lambda m: f"{m.group(1)}\n{REDACTED_TOKEN}", text)
    text = _ENV.sub(_env_repl, text)
    text = _TOKENS.sub(_token_repl, text)
    return text


def redact_obj(data: Any) -> Any:
    if isinstance(data, str):
        stripped = data.strip()
        if stripped[:1] in "[{":
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                return redact_text(data)
            if isinstance(parsed, (dict, list)):
                return json.dumps(redact_obj(parsed), ensure_ascii=False)
        return redact_text(data)
    if isinstance(data, list):
        return [redact_obj(x) for x in data]
    if isinstance(data, dict):
        return {k: redact_obj(v) for k, v in data.items()}
    return data


def redact(text: str) -> str:
    """Redact a string, including JSON-encoded tool arguments."""
    if not text:
        return text
    return redact_obj(text) if isinstance(text, str) else text


def secret_kinds(text: str) -> list[str]:
    """High-precision secret shapes in text. Empty means nothing to flag."""
    if not text:
        return []
    kinds: list[str] = []
    if REDACTED_TOKEN in text:
        kinds.append("token")
    if _PEM.search(text) or _PEM_DANGLING.search(text):
        kinds.append("private-key")
    for m in _TOKENS.finditer(text):
        tok = m.group(0)
        if tok.startswith("AKIA"):
            kinds.append("aws-key")
        elif tok.startswith("ghp_") or tok.startswith("github_pat_"):
            kinds.append("github-token")
        elif tok.startswith("sk_live_"):
            kinds.append("stripe-key")
        elif tok.startswith("xai-"):
            kinds.append("xai-key")
        elif tok.startswith("sk-"):
            kinds.append("api-key")
    out: list[str] = []
    for k in kinds:
        if k not in out:
            out.append(k)
    return out
