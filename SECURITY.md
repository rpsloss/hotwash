# Security

Hotwash reads local session files and writes reports. It does not call the
network except when *you* pass a trace that already contains a curl.

## Secrets

- `--dump-trace` and `--write-case` redact credential-shaped values (API
  tokens, PEM bodies, known env keys). Key names and paths stay.
- Fixtures use obvious fake keys (`sk-hotwashfixturekey00000001`), split
  concatenations in Python tests, or AWS-style EXAMPLE placeholders.
- Dummy alphabet strings may still appear in **git history** from earlier
  commits. They were never live keys. GitHub secret scanning alert #1 is
  that dummy. History was not rewritten.

If you freeze a real session, treat `cases/` as sensitive until you confirm
redaction. Do not commit live `.env` files.

## GitHub Action

`inputs.path` is passed through an environment variable, not interpolated
into the script text. Do not change that pattern.

## Write paths

`--write-case` rejects a relative dest that contains `..`. Absolute paths
are allowed (you asked for that location).

## Reporting

Open an issue on [rpsloss/hotwash](https://github.com/rpsloss/hotwash).
Do not file live secrets in the issue body.
