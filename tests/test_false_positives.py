from pathlib import Path

from hotwash.detectors import run_all
from hotwash.ingest import load
from hotwash.report import rank

FIXTURES = Path(__file__).parent / "fixtures"


def _assert_clean(path: Path) -> None:
    trace = load(path)
    findings = run_all(trace)
    assert findings == [], [f.line() for f in findings]
    assert rank(findings)[0] == "CLEAN"


def test_fp_docs_keyname_readme_placeholder_is_clean():
    _assert_clean(FIXTURES / "fp_docs_keyname.jsonl")


def test_fp_git_log_only_machine_local_email_is_clean():
    _assert_clean(FIXTURES / "fp_git_log_only.jsonl")
    _assert_clean(FIXTURES / "git_log.jsonl")


def test_fp_successful_curl_live_claim_is_clean():
    _assert_clean(FIXTURES / "fp_successful_curl.jsonl")


def test_fp_pytest_ok_tests_pass_is_clean():
    _assert_clean(FIXTURES / "fp_pytest_ok.jsonl")


def test_fp_aws_example_key_in_docs_is_clean():
    _assert_clean(FIXTURES / "fp_aws_example.jsonl")


def test_fp_docs_keyname_is_not_secret_write():
    _assert_clean(FIXTURES / "fp_docs_keyname.jsonl")
