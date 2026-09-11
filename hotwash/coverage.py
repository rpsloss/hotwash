from __future__ import annotations

from pathlib import Path

from hotwash.case import eval_dir
from hotwash.detectors import REGISTRY


def coverage(root: Path) -> dict:
    """Which REGISTRY detectors never fire on cases under root."""
    rows = eval_dir(Path(root))
    fired = sorted({name for row in rows for name in (row.get("detectors") or [])})
    registry = sorted(REGISTRY)
    missing = [name for name in registry if name not in set(fired)]
    return {
        "fired": fired,
        "registry": registry,
        "missing": missing,
        "cases": len(rows),
    }


def render_coverage(data: dict) -> str:
    """Text table of registry detectors vs whether a case fired them."""
    fired = set(data.get("fired") or [])
    registry = data.get("registry") or []
    lines = [
        "HOTWASH COVERAGE",
        "",
        f"{'DETECTOR':<24} STATUS",
    ]
    for name in registry:
        status = "fired" if name in fired else "no case"
        lines.append(f"{name:<24} {status}")
    n_fired = len(fired)
    n_reg = len(registry)
    lines.append("")
    lines.append(f"{n_fired}/{n_reg} detectors have a case")
    lines.append(f"cases: {data.get('cases', 0)}")
    missing = data.get("missing") or []
    if missing:
        lines.append("no case fired: " + ", ".join(missing))
    lines.append("")
    return "\n".join(lines)
