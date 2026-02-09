# Colab Runbook (GPU)

Use this runbook in a fresh Colab runtime.

## Setup
```bash
%cd /content
!git clone https://github.com/<YOUR_USERNAME>/policyLLM-support-bot.git
%cd /content/policyLLM-support-bot

!python -m pip install -U pip
!python -m pip install -e '.[train,dev]'
!python -m pip install -U "accelerate>=1.0.0,<2.0.0" "trl>=0.15.0,<1.0.0" "packaging>=24.0"
```

## Data
- Upload `kaggle.json` and set permissions.
- Download Olist + Twitter from Kaggle.
- Clone TweetSumm and copy files to `data/raw/tweetsumm/`.

## Build datasets
```bash
python pipelines/preprocess_text.py --raw-dir data/raw --processed-dir data/processed --max-rows 200000
python pipelines/build_dataset.py --raw-dir data/raw --processed-dir data/processed --max-cases 5000 --seed 42
```

## Train
```bash
python training/sft_train.py --model mistral-7b-instruct-v0.2 --train-cases data/processed/synthetic_cases_train.jsonl --val-cases data/processed/synthetic_cases_val.jsonl --tweetsumm data/processed/tweetsumm_pairs.jsonl --output-dir models/sft_qlora
python training/dpo_train.py --model mistral-7b-instruct-v0.2 --train-pairs data/processed/dpo_pairs_train.jsonl --output-dir models/dpo_qlora --adapter-init-dir models/sft_qlora/adapter
```

## Package artifacts
```bash
tar -czf trained_artifacts_final.tar.gz models data/processed/sft_* data/processed/dpo_*
```

Download `trained_artifacts_final.tar.gz` and attach it to a GitHub Release.
