# policyLLM-support-bot

Policy-grounded, stateful customer-support chatbot for refunds, returns, replacements, and escalations.

## Product summary
`policyLLM-support-bot` is an end-to-end conversational support system that combines:
- multi-turn guided chat UX,
- strict tool/function calling,
- deterministic policy enforcement,
- optional LLM assistance (hybrid/llm modes),
- evidence handling,
- and automated evaluation/release gates.

## What it does
- Runs a true chat flow until resolution, satisfaction, or explicit exit.
- Collects missing fields via guided UI controls (not guessing).
- Supports refund/return/replacement/cancel/escalation case types.
- Enforces policy server-side before any side-effect action.
- Logs tool calls, decisions, and timeline events for traceability.

## Core capabilities
- Session state + slot filling in Postgres
- Tool schemas with validated payloads
- Idempotent write tools for returns, labels, replacements, escalations
- Evidence upload + validation workflow
- Guardrails for prompt injection, fraud/bypass, and unsafe requests
- Resume-by-session support

## Technology used
- Backend APIs: `FastAPI`
- Database: `Postgres`
- UI: `Streamlit`
- Schemas/validation: `Pydantic`
- Model stack: `Transformers`, `PEFT`, `TRL` (SFT + DPO)
- Testing/linting: `pytest`, `ruff`
- Packaging/orchestration: `Docker`, `Docker Compose`
- CI/CD checks: `GitHub Actions`

## Architecture
```text
Web Chat UI (guided controls + timeline)
        |
        v
Agent Server
- state machine
- guardrails
- llm advisor routing
        |
        v
Tool Server
- policy and eligibility checks
- side-effect business tools
- evidence persistence and validation
        |
        v
Postgres + evidence storage
```

## LLM runtime modes
- `deterministic`: policy/state-machine only
- `hybrid`: LLM-assisted responses with deterministic fallback
- `llm`: LLM-required mode

Model runtime status is exposed at:
- `GET /chat/model/status`

## Public demo usage (when hosted)
1. Open the hosted chatbot URL.
2. Start a chat and provide an identifier (order id/email/phone-last4).
3. Follow guided controls for order, item, reason, and preferred resolution.
4. Upload evidence if requested.
5. Confirm satisfaction or request alternatives/escalation.
6. Use session resume to continue an existing case.

## Demo utility in UI
- Create test orders from the sidebar.
- View order list currently in system.
- Inspect case timeline and tool-driven status progression.

## Training and evaluation
The repo includes:
- synthetic data + conversation dataset builders,
- SFT preparation/training scripts,
- DPO preparation/training scripts,
- offline/conversational/safety eval suites,
- runtime and release readiness checks.

Primary datasets:
- Olist (orders/e-commerce)
- Customer Support on Twitter (language patterns)
- TweetSumm (summary supervision)

## Hosting this publicly
Yes, this project can be hosted as an online demo for anyone to use.

Recommended deployment:
1. `Render` or `Railway` with 3 services (`ui`, `agent_server`, `tool_server`) + managed Postgres.
2. Start public demos in `AGENT_MODE=deterministic`.
3. Switch to `AGENT_MODE=hybrid` after attaching trained adapter artifacts.

Deployment guide:
- `docs/ONLINE_DEPLOYMENT.md`

## Repository docs
- `docs/GITHUB_SETUP.md`
- `docs/COLAB_RUNBOOK.md`
- `docs/ONLINE_DEPLOYMENT.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/MODEL_STATUS.md`
- `docs/METRICS.md`
- `docs/PORTFOLIO_REPORT.md`

One-command release prep (with live demos):
```bash
python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md --run-demo --agent-url http://localhost:8002
```

Demo scenarios:
```bash
python3 scripts/demo_scenarios.py --agent-url http://localhost:8002 --output eval/results/demo_scenarios.json
```

Portfolio report:
```bash
python3 scripts/generate_portfolio_report.py --output docs/PORTFOLIO_REPORT.md
```

Release manifest:
```bash
python3 scripts/generate_manifest.py --repo-root . --output dist/release_manifest.json
```

Ship-ready gate:
```bash
python3 scripts/ship_ready_gate.py --repo-root . --max-age-hours 168 --output eval/results/ship_ready_gate.json
```
