# Contributing

Hotwash stays small. A detector is a function:

```python
def run(trace: Trace) -> list[Finding]:
    ...
```

Register it in `hotwash/detectors/__init__.py`. Add a fixture under
`tests/fixtures/` and a case in `tests/test_hotwash.py`.

Rules:

- Core path has no third-party dependencies.
- Detectors are deterministic. If you want a model judge, it is optional
  and behind `XAI_API_KEY`, default SpaceXAI (`https://api.x.ai/v1`).
- Do not add em dashes to user-facing copy. Yes, that is also a detector.
- Findings need evidence from the trace, not a vibe.
