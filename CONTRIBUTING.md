# Contributing Guide

Thanks for contributing to `policyLLM-support-bot`.

## Development Setup

```bash
cp .env.example .env
python3 -m pip install -e '.[dev]'
```

For full stack local run:

```bash
docker compose up --build
```

## Branch and PR Workflow

1. Create a branch from `main`.
2. Make focused changes with tests.
3. Run checks before opening PR:
   - `ruff check .`
   - `pytest -q`
4. Open PR with:
   - problem statement
   - change summary
   - validation output
   - screenshots for UI changes

## Coding Standards

- Python 3.11+ compatible.
- Keep functions small and deterministic when possible.
- Prefer strict schemas and explicit validation for API payloads.
- Keep secrets out of git; use `.env.example` for placeholders only.

## Testing Expectations

- Add/adjust tests for behavior changes.
- Preserve existing API contracts unless migration is documented.
- For chat-flow updates, include at least one end-to-end path test.

## Release Readiness

Before tagging a release:

```bash
python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md
```
