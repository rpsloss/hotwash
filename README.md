# HOTWASH

After-action review for coding-agent sessions.

The agent said it was done. The trace is the system of record.

Local. Deterministic. No cloud. No LLM required.

## Why

Coding agents ship claims: "it's live", "I verified", "pushed to main".
The session file already knows whether that is true. Hotwash reads the
trace and reports where the claim and the tools disagree.

This is the gap between "we ran an agent" and "we can improve the next one."
Evals that need a fresh Docker run are useful. Scoring the session you
already paid for is the missing loop.

## Install

Python 3.9+. No third-party dependencies.

```bash
git clone https://github.com/rpsloss/hotwash.git
cd hotwash
python3 -m pip install -e .
```

Or run from the repo with no install:

```bash
PYTHONPATH=. python3 -m hotwash path/to/session
```

## Use

Grok Build / Grok CLI session directory (has `chat_history.jsonl`):

```bash
hotwash ~/.grok/sessions/<workspace>/<session-id>
```

Generic JSONL (one event per line):

```bash
hotwash trace.jsonl --format md -o aar.md
hotwash trace.jsonl --format json
```

Exit code `1` if any finding is `error`. `0` if clean or warnings only.

## Detectors (v0)

| Detector | Error when |
| --- | --- |
| `emdash` | Agent wrote an em dash into a file |
| `git_identity` | `git commit` used a machine-local email (`user@Mac.lan`) GitHub cannot map |
| `ship_claim` | User asked to deploy / go live, and the trace has no curl, browser, or test |
| `todos` | Last `todo_write` still has pending items (warn) |

Each detector is a function `Trace -> list[Finding]`. Add one, add a test.

## What this is not

- Not an agent harness. It does not run the agent.
- Not LangSmith. Nothing leaves the machine.
- Not a C3PAO, not an authorizing official, and not a model eval leaderboard.

## Status

v0.1. Grok session ingest is real (this repo was dogfooded on a Grok Build
session). Generic JSONL is the interchange format. Claude Code / Codex
ingest and an optional SpaceXAI judge are next, not pretend-done.

## Develop

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest
```

## License

MIT
