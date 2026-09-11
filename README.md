# HOTWASH

After-action review for coding-agent sessions.

The agent said it was done. The trace is the system of record.

Local. Deterministic. No cloud. No LLM required.

## Why

Coding agents ship claims: "it's live", "I verified", "pushed to main".
The session file already knows whether that is true. Hotwash reads the
trace and reports where the claim and the tools disagree.

This is the gap between "we ran an agent" and "we can improve the next one."
Evals that re-run the agent in Docker are useful. Scoring the session you
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

```bash
hotwash --list                          # Grok and Claude sessions, newest first
hotwash --latest                        # review the newest Grok session
hotwash ~/.grok/sessions/<ws>/<id>      # a Grok session directory
hotwash ~/.claude/projects/<proj>/<id>.jsonl
hotwash trace.jsonl --format md -o aar.md
hotwash path --dump-trace               # normalized trace, no detectors
hotwash path --detectors emdash,tool_error
```

A Grok session directory contains `chat_history.jsonl`. Claude Code is a
JSONL whose events have a `message` object. Anything else with `role`/`type`
is generic JSONL. See [TRACE.md](TRACE.md).

Exit code `1` if any finding is `error`. `0` if clean or warnings only.

## Detectors (v0)

| Detector | Fires when |
| --- | --- |
| `tool_error` | A tool failed and was not retried; error if the assistant then claimed success |
| `ship_claim` | User asked to deploy or go live, and no *successful* curl, browser, or test ran |
| `emdash` | Agent **wrote** an em or en dash into a file (not when deleting one) |
| `git_identity` | `git commit` used a machine-local email GitHub cannot map |
| `todos` | Last `todo_write` still has pending items (warn) |

Each detector is `Trace -> list[Finding]`. Add one, add a test.

## What this is not

- Not an agent harness. It does not run the agent.
- Not a cloud trace product. Nothing leaves the machine.
- Not a model leaderboard.

## Status

v0. Grok and Claude Code ingest, generic JSONL, session list, dump-trace.
Codex ingest and an optional LLM judge are not in v0.

## Develop

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest
```

CI workflow lives at `contrib/test.yml`. Copy it to `.github/workflows/test.yml`
if the GitHub token has `workflow` scope.

## License

MIT
