# Design

Hotwash grades the log, not the briefing.

```
vendor session  -->  ingest adapter  -->  Trace  -->  detectors  -->  findings
                                         |                           |
                                         v                           v
                                   --dump-trace                 --write-case
                                                                   |
                                                                   v
                                                          cases/*.jsonl
                                                          cases/*.expect.json
                                                                   |
                                                                   v
                                                             hotwash --eval
```

## Layers

1. **Ingest.** Grok dirs, Claude Code JSONL, Codex rollout JSONL, Cursor
   agent-transcript JSONL, generic JSONL. Adapters only. Detectors never
   import a vendor parser.
2. **Trace.** `Message` + `ToolCall`. Failed work is `outcome=error` or `exit: 1`
   in `result`.
3. **Detectors.** `Trace -> list[Finding]`. Deterministic. High precision over
   recall. A CLEAN pin that starts failing is a bug in the detector, not in
   the user.
4. **Eval.** Portable JSONL plus expect sidecar. This is the product that
   compounds. The CLI is how you grow it.

## What we will not build

- An LLM judge. That reintroduces the failure mode.
- An agent runner. Different product.
- Cloud upload. The session stays on the machine.

## Parallel work (this window)

Landed: write_claim, read_claim, delete_claim, install_claim, branch_claim,
merge_claim, tag_claim, lint_claim, format_claim, Cursor ingest, ranked
`--list`, eval coverage.
Next slices own one new detector file plus its tests/fixtures only.
