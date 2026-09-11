from pathlib import Path

from hotwash.detectors import run_all
from hotwash.ingest import load
from hotwash.model import Finding
from hotwash.report import rank, render_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_html_tool_fail_rank_and_detectors():
    trace = load(FIXTURES / "tool_fail.jsonl")
    findings = run_all(trace)
    html = render_html(trace, findings)
    assert rank(findings)[0] == "FINDINGS"
    assert "FINDINGS" in html
    dets = {f.detector for f in findings}
    assert "tool_error" in dets
    assert "tests_claim" in dets
    for name in dets:
        assert name in html
    assert "<h1>Hotwash</h1>" in html
    assert "<table>" in html


def test_render_html_escapes_script_in_evidence():
    trace = load(FIXTURES / "tool_fail.jsonl")
    findings = list(run_all(trace))
    findings.append(
        Finding(
            detector="tool_error",
            severity="error",
            title="injected",
            detail='raw <script>alert(1)</script> in detail',
            evidence="<script>alert(1)</script>",
        )
    )
    html = render_html(trace, findings)
    assert "FINDINGS" in html
    assert "tool_error" in html
    assert "<script>" not in html
    assert "</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;/script&gt;" in html
