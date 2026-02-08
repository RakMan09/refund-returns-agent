# Portfolio Report: Refund/Returns Agent

## Product Overview
- Stateful multi-turn customer-support chatbot for refund/return/replacement/cancellation flows.
- Guided UI controls: dropdowns, multiselects, buttons, file upload, and timeline panel.
- Policy-authoritative backend with strict tool schemas and guardrails.

## Engineering Scope Implemented
- FastAPI tool server + agent server
- Postgres-backed sessions, chat messages, tool traces, and evidence records
- Streamlit conversational UI with test-order creation
- Deterministic policy engine and idempotent write tools
- Evaluation suites (offline, conversational, safety) + human rubric
- Training data pipelines for SFT and DPO (including conversation states)
- CI lint/tests + docker smoke checks + release automation

## Metrics Snapshot
- Offline decision_accuracy: 0.155
- Offline tool_validity_rate: 1.0
- Offline efficiency_rate: 1.0
- Conversational task_success_rate: 1.0
- Conversational avg_turns_to_resolution: 5
- Safety pass_rate: 0.8

## Operational Validation
- Final audit passed: True
- Demo scenarios generated: `eval/results/demo_scenarios.json`
- Release bundle automation available: `scripts/release_prep.py`

## Key Artifacts
- `docs/METRICS.md`
- `docs/RELEASE_SUMMARY.md`
- `docs/RELEASE_NOTES.md`
- `eval/results/eval_report.json`
- `eval/results/conversation_eval_report.json`
- `eval/results/safety_report.json`
- `eval/results/final_audit_report.json`

## Repro Commands
```bash
ruff check .
pytest -q
python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md
python3 scripts/demo_scenarios.py --agent-url http://localhost:8002 --output eval/results/demo_scenarios.json
```
