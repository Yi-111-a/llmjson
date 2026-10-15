# Changelog

## v0.1.0 — 2026-10-15

First release.

- `loads` / `extract` / `find` / `extract_all` / `repair` / `strip_reasoning` library API (stdlib only, Python 3.9+).
- Extraction from ```` ```json ```` fences (incl. unterminated), prose wrappers, and text with `<think>`-style reasoning blocks.
- Conservative repairs: trailing commas, comments, single quotes, Python literals, raw control characters in strings, mismatched closers, truncated output.
- `llmjson` CLI with `--raw`, `--indent`, `--strict`, `--repair-only`, `--find`, `--all`, `--ascii`; exit code 1 when nothing is recoverable.
