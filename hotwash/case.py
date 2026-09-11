from __future__ import annotations

import json
from pathlib import Path

from hotwash.detectors import run_all
from hotwash.ingest import load
from hotwash.model import Finding, Trace
from hotwash.report import rank


def trace_to_jsonl(trace: Trace) -> str:
    """Vendor-neutral JSONL. Detectors can load this without Grok or Claude."""
    lines: list[str] = []
    seen: set[str] = set()
    for msg in trace.messages:
        if msg.role == "system":
            continue
        row: dict = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            row["tool_calls"] = [
                {"id": t.id, "name": t.name, "arguments": t.arguments} for t in msg.tool_calls
            ]
        lines.append(json.dumps(row, ensure_ascii=False))
        for t in msg.tool_calls:
            if t.result or t.outcome:
                lines.append(
                    json.dumps(
                        {
                            "role": "tool",
                            "id": t.id,
                            "name": t.name,
                            "outcome": t.outcome,
                            "content": t.result,
                        },
                        ensure_ascii=False,
                    )
                )
            seen.add(t.id)
    for t in trace.tools:
        if t.id in seen:
            continue
        lines.append(
            json.dumps(
                {
                    "role": "tool",
                    "id": t.id,
                    "name": t.name,
                    "outcome": t.outcome,
                    "content": t.result,
                    "arguments": t.arguments,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) + ("\n" if lines else "")


def expect_from_findings(findings: list[Finding]) -> dict:
    label, _ = rank(findings)
    return {
        "rank": label,
        "must_include": sorted({f.detector for f in findings}),
    }


def write_case(trace: Trace, findings: list[Finding], dest: Path) -> tuple[Path, Path]:
    dest = Path(dest)
    if dest.suffix:
        stem = dest.with_suffix("")
    else:
        stem = dest
    stem.parent.mkdir(parents=True, exist_ok=True)
    jsonl = stem.with_suffix(".jsonl")
    expect = Path(str(stem) + ".expect.json")
    jsonl.write_text(trace_to_jsonl(trace))
    expect.write_text(json.dumps(expect_from_findings(findings), indent=2) + "\n")
    return jsonl, expect


def load_expect(path: Path) -> dict:
    return json.loads(path.read_text())


def check_case(findings: list[Finding], expect: dict) -> list[str]:
    """Return mismatch strings. Empty means the case passed."""
    problems: list[str] = []
    label, _ = rank(findings)
    got = {f.detector for f in findings}
    want_rank = expect.get("rank")
    if want_rank and label != want_rank:
        problems.append(f"rank {label} != {want_rank}")
    for name in expect.get("must_include") or []:
        if name not in got:
            problems.append(f"missing {name}")
    for name in expect.get("must_not_include") or []:
        if name in got:
            problems.append(f"unexpected {name}")
    return problems


def eval_dir(root: Path) -> list[dict]:
    """Evaluate every *.expect.json next to a *.jsonl (or Grok dir)."""
    root = Path(root)
    expects = sorted(root.glob("*.expect.json"))
    if not expects:
        raise ValueError(f"No *.expect.json under {root}")
    rows: list[dict] = []
    for exp_path in expects:
        name = exp_path.name[: -len(".expect.json")]
        jsonl = exp_path.parent / f"{name}.jsonl"
        grok = exp_path.parent / name
        if jsonl.exists():
            source = jsonl
        elif grok.is_dir():
            source = grok
        else:
            rows.append(
                {
                    "name": name,
                    "ok": False,
                    "rank": "-",
                    "expect_rank": load_expect(exp_path).get("rank", "-"),
                    "problems": ["no .jsonl (or session dir) next to expect file"],
                }
            )
            continue
        trace = load(source)
        findings = run_all(trace)
        label, _ = rank(findings)
        expect = load_expect(exp_path)
        problems = check_case(findings, expect)
        rows.append(
            {
                "name": name,
                "ok": not problems,
                "rank": label,
                "expect_rank": expect.get("rank", "-"),
                "problems": problems,
                "detectors": sorted({f.detector for f in findings}),
            }
        )
    return rows


def render_eval(rows: list[dict]) -> str:
    lines = [
        "HOTWASH EVAL",
        "",
        f"{'CASE':<24} {'GOT':<10} {'EXPECT':<10} STATUS",
    ]
    for row in rows:
        status = "ok" if row["ok"] else "FAIL " + "; ".join(row["problems"])
        lines.append(f"{row['name']:<24} {row['rank']:<10} {row['expect_rank']:<10} {status}")
    ok = sum(1 for r in rows if r["ok"])
    lines.append("")
    lines.append(f"{ok}/{len(rows)} passed")
    lines.append("")
    return "\n".join(lines)
