# Release Checklist

## Pre-release
- Confirm no secrets in repo (`.env` ignored, only `.env.example` committed).
- Run local quality checks:
  - `ruff check .`
  - `pytest -q`
- Rebuild and smoke test stack:
  - `docker compose up --build`
  - health checks for tool server, agent server, and UI
- Regenerate evaluation reports if model or guardrails changed:
  - `python3 eval/eval_harness.py ...`
  - `python3 eval/safety_suite.py ...`

## Versioning
- Update `README.md` with latest key metrics and known limitations.
- Create a tag:
  - `git tag -a v0.1.0 -m "Initial portfolio release"`
  - `git push origin v0.1.0`

## Release assets
- Upload non-repo model artifacts to GitHub Release assets or cloud storage:
  - SFT adapter (if available)
  - DPO adapter
  - Optional packed artifact tarball
- Add links in release notes.
- Generate release summary + bundle:
  - `python3 scripts/generate_metrics_snapshot.py --output docs/METRICS.md`
  - `python3 scripts/generate_portfolio_report.py --output docs/PORTFOLIO_REPORT.md`
  - `python3 scripts/generate_manifest.py --repo-root . --output dist/release_manifest.json`
  - `python3 scripts/build_release_bundle.py --repo-root . --output-dir dist --release-summary docs/RELEASE_SUMMARY.md`
  - `python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md`
  - Optional full run with live demos: `python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md --run-demo --agent-url http://localhost:8002`

## Post-release
- Verify GitHub Actions CI passed on the tagged commit.
- Confirm README links and setup instructions work from a clean clone.
