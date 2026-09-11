from __future__ import annotations

import re

from hotwash.detectors.util import blob, failed
from hotwash.model import Finding, Trace

CLAIM = re.compile(
    r"\b(all tests pass(?:ed)?|tests pass(?:ed)?|pytest.*pass(?:ed)?)\b",
    re.I,
)
ASK = re.compile(r"\b(run (the )?tests|write tests|unit tests|pytest)\b", re.I)
TEST_HINT = re.compile(
    r"\b(pytest|npm test|npx vitest|vitest|cargo test|go test|python -m unittest)\b",
    re.I,
)


def run(trace: Trace) -> list[Finding]:
    test_ok = [t for t in trace.tools if TEST_HINT.search(blob(t)) and not failed(t)]
    claimed = bool(CLAIM.search(trace.assistant_text()))
    asked = bool(ASK.search(trace.user_text()))
    if claimed and not test_ok:
        return [
            Finding(
                detector="tests_claim",
                severity="error",
                title="claimed tests passed without a successful test run",
                detail="The assistant said tests passed. The trace has no successful pytest / npm test / equivalent.",
                evidence=_snip(trace.assistant_text()),
            )
        ]
    if asked and not test_ok and not claimed:
        return [
            Finding(
                detector="tests_claim",
                severity="warn",
                title="tests were requested; no test runner in the trace",
                detail="The user asked to run or write tests. No test command succeeded.",
                evidence=_snip(trace.user_text()),
            )
        ]
    return []


def _snip(text: str, n: int = 240) -> str:
    text = " ".join(text.split())
    return text[:n]
