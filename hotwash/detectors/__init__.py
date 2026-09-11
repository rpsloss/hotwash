from __future__ import annotations

from collections.abc import Callable

from hotwash.detectors.emdash import run as emdash_run
from hotwash.detectors.git_identity import run as git_identity_run
from hotwash.detectors.ship_claim import run as ship_claim_run
from hotwash.detectors.todos import run as todos_run
from hotwash.model import Finding, Trace

Detector = Callable[[Trace], list[Finding]]

DETECTORS: list[Detector] = [
    emdash_run,
    git_identity_run,
    ship_claim_run,
    todos_run,
]


def run_all(trace: Trace) -> list[Finding]:
    out: list[Finding] = []
    for det in DETECTORS:
        out.extend(det(trace))
    order = {"error": 0, "warn": 1, "info": 2}
    out.sort(key=lambda f: (order.get(f.severity, 9), f.detector, f.title))
    return out
