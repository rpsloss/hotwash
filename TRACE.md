# Trace format

Detectors do not read Grok or Claude files. They read a `Trace`:
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

## Adapters

| Source | How hotwash detects it |
| --- | --- |
| Grok session dir | directory containing `chat_history.jsonl` |
| Claude Code JSONL | file whose events have `type` plus a `message` object |
| Generic JSONL | anything else with `role` / `type` |

`--dump-trace` prints the normalized form (results truncated). Use that when
adding an adapter: dump, then write a detector against the dump, not the
vendor file.

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

## Adding an ingest

1. Parse vendor log into `Message` and `ToolCall`.
2. Put failed tools in `ToolCall.outcome = "error"` (or leave a `exit: 1` line
   in `result`).
3. Add a sniff rule in `hotwash/ingest/sniff.py`.
4. Add a fixture under `tests/fixtures/` and a load test.
