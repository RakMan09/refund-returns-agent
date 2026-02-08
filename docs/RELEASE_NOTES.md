# Release Notes Template

## Summary
- End-to-end Refund/Returns Agent portfolio release.
- Includes services, pipelines, training scripts, eval harness, safety suite, and UI.

## What Changed
- Tool server + policy engine + idempotent write tools
- Agent server orchestration + guardrails
- Synthetic data + SFT/DPO preparation/training scripts
- Eval harness + safety suite + human rubric
- Streamlit UI + trace/report views
- CI, docs, release hardening

## Metrics Snapshot
- Offline eval:
  - decision_accuracy: 0.155
  - tool_validity_rate: 1.0
  - sequence_correct_rate: 0.0
  - efficiency_rate: 1.0
- Safety suite:
  - pass_rate: 0.8

## Artifacts
- SFT adapter: <link>
- DPO adapter: <link>
- Optional bundle: <link>

## Known Limitations
- Full QLoRA training requires CUDA host.
- Baseline decision accuracy/safety should be improved with additional iterations.

## Repro Steps
- See README sections: Local Setup, Public Data Ingestion, Training, Evaluation.
