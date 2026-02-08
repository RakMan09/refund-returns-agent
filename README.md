# refund-returns-agent

Multi-turn, policy-grounded Refund/Returns chatbot portfolio project.

This repo now supports a stateful conversational UX (session-based) and is being expanded checkpoint-by-checkpoint to full end-to-end training/eval/guardrails.

## Current Scope (Checkpoint 17 of multi-turn upgrade)
Implemented conversational flow + evidence pipeline + eval + training data + CI + release prep + portfolio artifacts + release gate + optional live-demo release mode:
- Postgres-backed chat sessions and state memory
- Guided chatbot controls (dropdowns, multiselect, buttons, upload placeholder)
- New interactive tools:
  - `list_orders(customer_identifier)`
  - `list_order_items(order_id)`
  - `set_selected_order(session_id, order_id)`
  - `set_selected_items(session_id, item_ids)`
  - `create_test_order(payload)`
  - `get_case_status(case_id)`
  - `upload_evidence(session_id, file_metadata+content)`
  - `get_evidence(case_id)`
  - `validate_evidence(evidence_id, order_id, item_id)`
- New chat endpoints:
  - `POST /chat/start`
  - `POST /chat/message`
  - `POST /chat/create_test_order`
- Streamlit chat UI with timeline panel + create-test-order panel + real image upload
- Expanded case handling paths:
  - refund request
  - return request
  - replacement request
  - cancel order (if processing)
  - missing/wrong item
  - damaged item requiring evidence
  - late delivery
  - no order id fallback via email/phone last4
- Satisfaction loop with deterministic alternatives:
  - replacement
  - store credit
  - escalation
- Explicit termination support:
  - user satisfaction = yes
  - explicit exit message
  - terminal waiting states + status check (`status` message)
- Approach B evidence simulation:
  - local object storage for uploaded files (`data/evidence/`)
  - deterministic anomaly/evidence plausibility scoring
  - optional dataset hooks via `.env` paths:
    - `APPROACH_B_CATALOG_DIR`
    - `APPROACH_B_ANOMALY_DIR`
- New conversational eval harness:
  - `eval/conversation_eval.py`
  - reports: task success rate, turns-to-resolution, slot-filling accuracy, evidence handling accuracy
  - exports chat transcripts for human rating (`eval/results/conversation_transcripts.jsonl`)
- New multi-turn training dataset builder:
  - `pipelines/build_conversation_dataset.py`
  - outputs conversation SFT records + DPO preference pairs
  - supports evidence-required chat states and guided-control decisions
- DPO prep now supports mixed pair sources:
  - baseline policy/tool pairs (`dpo_pairs_train.jsonl`)
  - conversation preference pairs (`conversation_dpo_pairs_train.jsonl`)
  - configurable limits per source
- End-to-end stack smoke script:
  - `eval/stack_smoke.py` validates health, guided chat, evidence upload, validation, and terminal resolution
  - wired into CI via `docker-smoke` job
- Final publish audit:
  - `scripts/final_audit.py` checks required files, `.env` tracking, and secret-like patterns
  - output report: `eval/results/final_audit_report.json`
- Metrics snapshot generator:
  - `scripts/generate_metrics_snapshot.py` creates `docs/METRICS.md` from latest eval/safety/conversation/audit reports
- Release bundle generator:
  - `scripts/build_release_bundle.py` creates `docs/RELEASE_SUMMARY.md` + versioned `dist/release_bundle_*.tar.gz`
- Release prep automation:
  - `scripts/release_prep.py` runs final audit + metrics snapshot + release bundle + filled release notes
- Demo scenarios automation:
  - `scripts/demo_scenarios.py` runs deterministic multi-turn demos (damaged+evidence, escalation, cancel-processing)
  - outputs `eval/results/demo_scenarios.json` for portfolio evidence/screenshots
- Portfolio report automation:
  - `scripts/generate_portfolio_report.py` builds `docs/PORTFOLIO_REPORT.md` from latest artifacts/metrics
- Release manifest automation:
  - `scripts/generate_manifest.py` builds `dist/release_manifest.json` with file hashes/sizes
  - integrated into `scripts/release_prep.py`
- Collaboration/community health files:
  - `CONTRIBUTING.md`
  - `SECURITY.md`
  - `.github/pull_request_template.md`
  - `.github/ISSUE_TEMPLATE/bug_report.md`
  - `.github/ISSUE_TEMPLATE/feature_request.md`
- Ship-ready release gate:
  - `scripts/ship_ready_gate.py` checks required release artifacts exist and are fresh
  - outputs `eval/results/ship_ready_gate.json`
- Release prep full mode:
  - `scripts/release_prep.py --run-demo --agent-url ...` regenerates demo scenarios before packaging
  - useful for final demo-first portfolio release refresh
- GitHub publishing playbook:
  - `docs/GITHUB_SETUP.md`

## Architecture
```text
Streamlit Chat UI
  - chat history
  - guided controls
  - test order form
  - timeline panel
         |
         v
Agent Server (FastAPI)
  - chat state machine (slot-filling foundation)
  - guardrails
  - guided next-control decisions
         |
         v
Tool Server (FastAPI)
  - order/policy/refund tools
  - chat session persistence tools
  - test order creation
         |
         v
Postgres
  - orders, returns, labels, escalations
  - chat_sessions, chat_messages
  - tool_call_logs
```

## Run Locally
```bash
cd "/Users/raksh/Desktop/Refund Returns Agent"
cp .env.example .env
docker compose up --build
```

Open:
- UI: `http://localhost:8501`
- Tool server health: `http://localhost:8001/health`
- Agent server health: `http://localhost:8002/health`

## Chat Demo Flow
1. Start new chat in sidebar.
2. Provide identifier (order id / email / phone last4).
3. Select order from dropdown.
4. Select items from multiselect.
5. Select reason.
6. If damaged, upload evidence image; backend stores + validates it before resolution.
7. Bot resolves or asks follow-up and asks satisfaction.

## Create Test Order (for demos)
In UI sidebar, fill “Create Test Order”, submit, then use that customer email/phone to test the chat flow immediately.

## Data + Training + Evaluation
Existing data/training/eval scripts remain available:
- `pipelines/preprocess_text.py`
- `pipelines/build_dataset.py`
- `training/sft_train.py`
- `training/dpo_train.py`
- `eval/eval_harness.py`
- `eval/conversation_eval.py`
- `eval/safety_suite.py`

Run evals:
```bash
python3 eval/eval_harness.py --dataset data/processed/synthetic_cases_test.jsonl --agent-url http://localhost:8002 --limit 200 --output eval/results/eval_report.json
python3 eval/conversation_eval.py --agent-url http://localhost:8002 --output eval/results/conversation_eval_report.json --transcripts-output eval/results/conversation_transcripts.jsonl
python3 eval/safety_suite.py --agent-url http://localhost:8002 --output eval/results/safety_report.json
python3 eval/stack_smoke.py --agent-url http://localhost:8002 --tool-url http://localhost:8001
```

Build conversation training data:
```bash
python3 pipelines/build_conversation_dataset.py \
  --train-cases data/processed/synthetic_cases_train.jsonl \
  --val-cases data/processed/synthetic_cases_val.jsonl \
  --output-sft-train data/processed/conversation_sft_train.jsonl \
  --output-sft-val data/processed/conversation_sft_val.jsonl \
  --output-dpo-train data/processed/conversation_dpo_pairs_train.jsonl
```

Use the generated conversation SFT records in prep:
```bash
python3 training/sft_train.py \
  --prepare-only \
  --conversation-records-train data/processed/conversation_sft_train.jsonl \
  --conversation-records-val data/processed/conversation_sft_val.jsonl
```

Use mixed DPO pair sources in prep:
```bash
python3 training/dpo_train.py \
  --prepare-only \
  --train-pairs data/processed/dpo_pairs_train.jsonl \
  --conversation-train-pairs data/processed/conversation_dpo_pairs_train.jsonl \
  --prepared-train data/processed/dpo_train_prepared.jsonl \
  --prepared-val data/processed/dpo_val_prepared.jsonl
```

Convenience make targets:
```bash
make build-conversation-data
make conversation-eval
make prepare-dpo-mixed
make stack-smoke
```

## Quality
```bash
ruff check .
pytest -q
```

## GitHub + Release
- CI workflow: `.github/workflows/ci.yml`
- Release checklist: `docs/RELEASE_CHECKLIST.md`
- Colab runbook: `docs/COLAB_RUNBOOK.md`
- GitHub setup guide: `docs/GITHUB_SETUP.md`
- License: `LICENSE` (MIT)

Final audit:
```bash
python3 scripts/final_audit.py --output eval/results/final_audit_report.json
```

Metrics snapshot:
```bash
python3 scripts/generate_metrics_snapshot.py --output docs/METRICS.md
```

Release bundle:
```bash
python3 scripts/build_release_bundle.py --repo-root . --output-dir dist --release-summary docs/RELEASE_SUMMARY.md
```

One-command release prep:
```bash
python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md
```

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
