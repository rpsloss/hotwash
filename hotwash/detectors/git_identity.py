from __future__ import annotations

import re

from hotwash.model import Finding, Trace

HOST_EMAIL = re.compile(r"@Mac\.lan\b|@[^.\s]+\.local\b", re.I)
AUTO_IDENT = "configured automatically based on your username and hostname"
COMMIT_CMD = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*commit\b")


def run(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    for tool in trace.tools_named("run_terminal_command", "bash", "shell"):
        args = tool.args_dict()
        cmd = str(args.get("command") or args.get("cmd") or tool.arguments)
        if not COMMIT_CMD.search(cmd):
            continue
        attributed = (
            "users.noreply.github.com" in cmd
            or "GIT_AUTHOR_EMAIL" in cmd
            or "user.email" in cmd
        )
        if HOST_EMAIL.search(tool.result) or AUTO_IDENT in tool.result:
            findings.append(
                Finding(
                    detector="git_identity",
                    severity="error",
                    title="git commit used a machine-local identity",
                    detail="GitHub cannot map this author. Vercel Hobby deploys from private repos will be blocked until the author is a verified GitHub user.",
                    evidence=_snip(cmd + "\n" + tool.result),
                )
            )
        elif not attributed:
            findings.append(
                Finding(
                    detector="git_identity",
                    severity="warn",
                    title="git commit did not set a GitHub-mapped author",
                    detail="Pass -c user.email='ID+login@users.noreply.github.com' on the commit so Vercel can verify the author.",
                    evidence=_snip(cmd),
                )
            )
    return findings


def _snip(text: str, n: int = 400) -> str:
    return text[:n]
