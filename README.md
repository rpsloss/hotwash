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
hotwash --list                          # Grok, Claude, Codex, Cursor
hotwash --list --rank                   # rank, error detectors, first prompt
hotwash --coverage cases                # detectors with no case yet
hotwash --latest                        # newest Grok, Claude, or Codex session
hotwash ~/.grok/sessions/<ws>/<id>      # a Grok session directory
hotwash ~/.claude/projects/<proj>/<id>.jsonl
hotwash ~/.codex/sessions/2026/09/11/rollout-*.jsonl
hotwash trace.jsonl --format md -o aar.md
hotwash path --format html -o aar.html  # shareable AAR
hotwash path --dump-trace               # normalized trace, no detectors
hotwash path --detectors emdash,tool_error
hotwash path --strict                   # warnings fail the process
hotwash path --quiet                    # rank and finding lines only
hotwash path --write-case cases/name    # freeze as portable JSONL + expect
hotwash --eval cases                    # run the case suite
cat trace.jsonl | hotwash -
```

GitHub Action (from another repo):

```yaml
- uses: rpsloss/hotwash@main
  with:
    path: cases
```

A Grok session directory contains `chat_history.jsonl`. Claude Code is a
JSONL whose events have a `message` object. Codex CLI is a rollout JSONL
under `~/.codex/sessions`. Anything else with `role`/`type` is generic
JSONL. See [TRACE.md](TRACE.md).

Exit code `1` if any finding is `error`. `0` if clean or warnings only.
`--strict` exits `1` on warnings too.

## Detectors (v0)

| Detector | Fires when |
| --- | --- |
| `tool_error` | A tool failed and was not retried; error if the assistant then claimed success |
| `tests_claim` | Assistant said tests passed, and no successful test runner is in the trace |
| `ship_claim` | User asked to deploy or go live, and no curl, browser, or test ran |
| `verify_http` | User asked to ship (or the assistant claimed live) and the last curl/wget returned 4xx/5xx or a connection failure |
| `stale_verify` | User asked to ship (or the assistant claimed live) and the last curl/wget ran *before* the last write or push |
| `push_claim` | User asked to git push, or the assistant claimed a push, and no successful `git push` ran |
| `pr_claim` | User asked to open a PR, or the assistant claimed a PR, and no successful `gh pr create` ran |
| `refused_action` | User said not to push or commit, and a successful git push or git commit still ran |
| `commit_claim` | User asked to commit, or the assistant claimed a commit, and no successful `git commit` ran |
| `refused_action` | User said not to push or commit, and the agent did it anyway |
| `write_claim` | Assistant claimed it wrote/updated a file, and no successful write tool ran |
| `secret_write` | Agent wrote a credential-shaped secret (token or private key) into a file |
| `emdash` | Agent **wrote** an em or en dash into a file (not when deleting one) |
| `git_identity` | `git commit` used a machine-local email GitHub cannot map |
| `todos` | Last `todo_write` still has pending items (warn) |

Each detector is `Trace -> list[Finding]`. Add one, add a test.

## What this is not

- Not an agent harness. It does not run the agent.
- Not a cloud trace product. Nothing leaves the machine.
- Not a model leaderboard.

## Status

v0. Grok, Claude Code, and Codex ingest, generic JSONL, session list,
dump-trace, write-case (secrets redacted), and `hotwash --eval`. An
optional LLM judge is not in v0.

## Develop

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest
PYTHONPATH=. python3 -m hotwash --eval cases
```

CI workflow lives at `contrib/test.yml`. Copy it to `.github/workflows/test.yml`
if the GitHub token has `workflow` scope.

## License

MIT
