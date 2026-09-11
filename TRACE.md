# Trace format

Detectors do not read Grok, Claude, or Codex files. They read a `Trace`:
messages and tool calls. Ingest adapters turn vendor logs into that shape.

## Generic JSONL (the interchange)

One JSON object per line.

User / assistant:

```json
{"role":"user","content":"deploy this"}
{"role":"assistant","content":"I'll ship it.","tool_calls":[{"id":"c1","name":"run_terminal_command","arguments":"{\"command\":\"curl -sI https://example.com\"}"}]}
```

Tool result:

```json
{"role":"tool","id":"c1","name":"run_terminal_command","outcome":"success","content":"HTTP/2 200"}
```

`arguments` may be a JSON string or an object. `outcome` is `success` or `error`.
Shell tools may pass `command` as a string or as an argv list (`["git","push"]`).

## Adapters

| Source | How hotwash detects it |
| --- | --- |
| Grok session dir | directory containing `chat_history.jsonl` |
| Claude Code JSONL | file whose events have `type` plus a `message` object |
| Codex CLI JSONL | file whose events have `type` in `session_meta` / `response_item` / `event_msg` plus a `payload` object |
| Generic JSONL | anything else with `role` / `type` |

`--dump-trace` prints the normalized form (results truncated). Use that when
adding an adapter: dump, then write a detector against the dump, not the
vendor file.

Codex tool names (`shell`, `apply_patch`, `exec_command`) are first-class.
`apply_patch` counts as a write. `Exit code: 1` in a tool result counts as
failure, same as `exit: 1`.

## Eval cases

A case is two files with the same stem:

```
cases/tool_fail.jsonl
cases/tool_fail.expect.json
```

`expect.json`:

```json
{
  "rank": "FINDINGS",
  "must_include": ["tool_error", "tests_claim"],
  "must_not_include": []
}
```

Freeze a real session (writes portable JSONL, not the vendor log):

```bash
hotwash ~/.grok/sessions/<id> --write-case cases/ship-without-curl
hotwash --eval cases
```

`must_include` is the regression pin. If a detector stops firing, the case fails.
`hotwash --eval` also prints which detectors fired and which never fired in
the suite.

`--write-case` and `--dump-trace` redact credential-shaped tokens, PEM bodies,
and known env-key values. Key names and paths stay. Placeholder values such as
`your-key-here` are left alone. Token stand-ins keep `secret_write` firing so a
frozen case still pins the detector.

## Adding an ingest

1. Parse vendor log into `Message` and `ToolCall`.
2. Put failed tools in `ToolCall.outcome = "error"` (or leave a `exit: 1` line
   in `result`).
3. Add a sniff rule in `hotwash/ingest/sniff.py`.
4. Add a fixture under `tests/fixtures/` and a load test.
