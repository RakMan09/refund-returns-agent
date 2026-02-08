PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e .[dev]

run-tool-server:
	uvicorn services.tool_server.app.main:app --host 0.0.0.0 --port 8001 --reload

run-agent-server:
	uvicorn services.agent_server.app.main:app --host 0.0.0.0 --port 8002 --reload

run-ui:
	streamlit run services/ui/app.py --server.address 0.0.0.0 --server.port 8501

test:
	pytest

preprocess-text:
	python3 pipelines/preprocess_text.py --raw-dir data/raw --processed-dir data/processed

build-dataset:
	python3 pipelines/build_dataset.py --raw-dir data/raw --processed-dir data/processed --max-cases 5000 --seed 42

eval:
	python3 eval/eval_harness.py --dataset data/processed/synthetic_cases_test.jsonl --agent-url http://localhost:8002 --limit 200 --output eval/results/eval_report.json

conversation-eval:
	python3 eval/conversation_eval.py --agent-url http://localhost:8002 --output eval/results/conversation_eval_report.json --transcripts-output eval/results/conversation_transcripts.jsonl

safety:
	python3 eval/safety_suite.py --agent-url http://localhost:8002 --output eval/results/safety_report.json

stack-smoke:
	python3 eval/stack_smoke.py --agent-url http://localhost:8002 --tool-url http://localhost:8001

build-conversation-data:
	python3 pipelines/build_conversation_dataset.py --train-cases data/processed/synthetic_cases_train.jsonl --val-cases data/processed/synthetic_cases_val.jsonl --output-sft-train data/processed/conversation_sft_train.jsonl --output-sft-val data/processed/conversation_sft_val.jsonl --output-dpo-train data/processed/conversation_dpo_pairs_train.jsonl

prepare-sft:
	python3 training/sft_train.py --prepare-only --train-cases data/processed/synthetic_cases_train.jsonl --val-cases data/processed/synthetic_cases_val.jsonl --tweetsumm data/processed/tweetsumm_pairs.jsonl --prepared-train data/processed/sft_train_prepared.jsonl --prepared-val data/processed/sft_val_prepared.jsonl

prepare-dpo:
	python3 training/dpo_train.py --prepare-only --train-pairs data/processed/dpo_pairs_train.jsonl --prepared-train data/processed/dpo_train_prepared.jsonl --prepared-val data/processed/dpo_val_prepared.jsonl

prepare-dpo-mixed:
	python3 training/dpo_train.py --prepare-only --train-pairs data/processed/dpo_pairs_train.jsonl --conversation-train-pairs data/processed/conversation_dpo_pairs_train.jsonl --prepared-train data/processed/dpo_train_prepared.jsonl --prepared-val data/processed/dpo_val_prepared.jsonl

preflight:
	ruff check .
	pytest -q
	python3 -m compileall services pipelines training eval tests docs
	python3 scripts/final_audit.py --output eval/results/final_audit_report.json

lint:
	ruff check .

format:
	ruff format .

up:
	docker compose up --build

down:
	docker compose down

final-audit:
	python3 scripts/final_audit.py --output eval/results/final_audit_report.json

metrics-snapshot:
	python3 scripts/generate_metrics_snapshot.py --eval-report eval/results/eval_report.json --conversation-report eval/results/conversation_eval_report.json --safety-report eval/results/safety_report.json --audit-report eval/results/final_audit_report.json --output docs/METRICS.md

release-bundle:
	python3 scripts/build_release_bundle.py --repo-root . --output-dir dist --release-summary docs/RELEASE_SUMMARY.md

release-prep:
	python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md

release-prep-full:
	python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md --run-demo --agent-url http://localhost:8002

demo-scenarios:
	python3 scripts/demo_scenarios.py --agent-url http://localhost:8002 --output eval/results/demo_scenarios.json

portfolio-report:
	python3 scripts/generate_portfolio_report.py --output docs/PORTFOLIO_REPORT.md

manifest:
	python3 scripts/generate_manifest.py --repo-root . --output dist/release_manifest.json

ship-ready:
	python3 scripts/ship_ready_gate.py --repo-root . --max-age-hours 168 --output eval/results/ship_ready_gate.json
