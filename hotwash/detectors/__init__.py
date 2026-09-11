from __future__ import annotations

from collections.abc import Callable, Iterable

from hotwash.detectors.branch_claim import run as branch_claim_run
from hotwash.detectors.commit_claim import run as commit_claim_run
from hotwash.detectors.delete_claim import run as delete_claim_run
from hotwash.detectors.emdash import run as emdash_run
from hotwash.detectors.format_claim import run as format_claim_run
from hotwash.detectors.git_identity import run as git_identity_run
from hotwash.detectors.install_claim import run as install_claim_run
from hotwash.detectors.lint_claim import run as lint_claim_run
from hotwash.detectors.merge_claim import run as merge_claim_run
from hotwash.detectors.pr_claim import run as pr_claim_run
from hotwash.detectors.push_claim import run as push_claim_run
from hotwash.detectors.read_claim import run as read_claim_run
from hotwash.detectors.refused_action import run as refused_action_run
from hotwash.detectors.secret_write import run as secret_write_run
from hotwash.detectors.ship_claim import run as ship_claim_run
from hotwash.detectors.stale_verify import run as stale_verify_run
from hotwash.detectors.tag_claim import run as tag_claim_run
from hotwash.detectors.tests_claim import run as tests_claim_run
from hotwash.detectors.todos import run as todos_run
from hotwash.detectors.tool_error import run as tool_error_run
from hotwash.detectors.verify_http import run as verify_http_run
from hotwash.detectors.write_claim import run as write_claim_run
from hotwash.model import Finding, Trace

Detector = Callable[[Trace], list[Finding]]

REGISTRY: dict[str, Detector] = {
    "branch_claim": branch_claim_run,
    "commit_claim": commit_claim_run,
    "delete_claim": delete_claim_run,
    "emdash": emdash_run,
    "format_claim": format_claim_run,
    "git_identity": git_identity_run,
    "install_claim": install_claim_run,
    "lint_claim": lint_claim_run,
    "merge_claim": merge_claim_run,
    "pr_claim": pr_claim_run,
    "push_claim": push_claim_run,
    "read_claim": read_claim_run,
    "refused_action": refused_action_run,
    "secret_write": secret_write_run,
    "ship_claim": ship_claim_run,
    "stale_verify": stale_verify_run,
    "tag_claim": tag_claim_run,
    "tests_claim": tests_claim_run,
    "todos": todos_run,
    "tool_error": tool_error_run,
    "verify_http": verify_http_run,
    "write_claim": write_claim_run,
}


def run_all(trace: Trace, names: Iterable[str] | None = None) -> list[Finding]:
    if names is None:
        selected = list(REGISTRY.values())
    else:
        selected = []
        unknown = []
        for name in names:
            fn = REGISTRY.get(name)
            if fn is None:
                unknown.append(name)
            else:
                selected.append(fn)
        if unknown:
            raise ValueError(
                "Unknown detector(s): "
                + ", ".join(unknown)
                + ". Available: "
                + ", ".join(REGISTRY)
            )
    out: list[Finding] = []
    for det in selected:
        out.extend(det(trace))
    order = {"error": 0, "warn": 1, "info": 2}
    out.sort(key=lambda f: (order.get(f.severity, 9), f.detector, f.title))
    return out
