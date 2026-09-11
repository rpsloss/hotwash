import json
from pathlib import Path

from hotwash.coverage import coverage, render_coverage
from hotwash.detectors import REGISTRY

FIXTURES = Path(__file__).parent / "fixtures"


def _one_case(tmp_path: Path, fixture: str, expect: dict) -> Path:
    src = FIXTURES / fixture
    dest = tmp_path / fixture
    dest.write_text(src.read_text())
    stem = dest.stem
    (tmp_path / f"{stem}.expect.json").write_text(json.dumps(expect) + "\n")
    return tmp_path


def test_coverage_one_case_lists_untriggered_detectors(tmp_path):
    root = _one_case(
        tmp_path,
        "tool_fail.jsonl",
        {"rank": "FINDINGS", "must_include": ["tests_claim", "tool_error"]},
    )
    data = coverage(root)
    assert data["cases"] == 1
    assert data["registry"] == sorted(REGISTRY)
    assert data["fired"] == ["tests_claim", "tool_error"]
    assert data["missing"] == sorted(set(data["registry"]) - set(data["fired"]))
    assert "secret_write" in data["missing"]
    assert "pr_claim" in data["missing"]
    assert "emdash" in data["missing"]
    assert "tool_error" not in data["missing"]


def test_render_coverage_text_table(tmp_path):
    root = _one_case(
        tmp_path,
        "tool_fail.jsonl",
        {"rank": "FINDINGS", "must_include": ["tool_error"]},
    )
    text = render_coverage(coverage(root))
    assert text.startswith("HOTWASH COVERAGE")
    assert "DETECTOR" in text.splitlines()[2]
    assert "STATUS" in text.splitlines()[2]
    assert "tool_error" in text
    assert "tests_claim" in text
    assert "secret_write" in text
    assert "no case" in text
    assert "fired" in text
    assert "no case fired:" in text
    assert "cases: 1" in text
