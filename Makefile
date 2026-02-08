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

safety:
	python3 eval/safety_suite.py --agent-url http://localhost:8002 --output eval/results/safety_report.json

prepare-sft:
	python3 training/sft_train.py --prepare-only --train-cases data/processed/synthetic_cases_train.jsonl --val-cases data/processed/synthetic_cases_val.jsonl --tweetsumm data/processed/tweetsumm_pairs.jsonl --prepared-train data/processed/sft_train_prepared.jsonl --prepared-val data/processed/sft_val_prepared.jsonl

prepare-dpo:
	python3 training/dpo_train.py --prepare-only --train-pairs data/processed/dpo_pairs_train.jsonl --prepared-train data/processed/dpo_train_prepared.jsonl --prepared-val data/processed/dpo_val_prepared.jsonl

preflight:
	ruff check .
	pytest -q
	python3 -m compileall services pipelines training eval tests docs

lint:
	ruff check .

format:
	ruff format .

up:
	docker compose up --build

down:
	docker compose down
