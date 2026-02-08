from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any

MODEL_PRESETS = {
    "mistral-7b-instruct-v0.2": "mistralai/Mistral-7B-Instruct-v0.2",
    "llama-3.1-8b-instruct": "meta-llama/Llama-3.1-8B-Instruct",
    "qwen2.5-7b-instruct": "Qwen/Qwen2.5-7B-Instruct",
}


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def load_text_records(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    rows = load_jsonl(path, limit=limit)
    out: list[dict[str, str]] = []
    for row in rows:
        text = row.get("text")
        if isinstance(text, str) and text.strip():
            out.append({"source": str(row.get("source", "conversation_synthetic")), "text": text})
    return out


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def synthesize_customer_reply(decision: dict[str, Any], reason: str) -> str:
    action = decision.get("next_action", "request_info")
    amount = decision.get("refund_amount", "0.00")
    missing = decision.get("missing_info", [])
    reason_text = decision.get("decision_reason", "policy constraints")

    if action == "deny":
        return (
            "Thanks for your request. Based on policy, this case is not eligible for refund/return: "
            f"{reason_text}."
        )
    if action == "request_info":
        missing_text = ", ".join(missing) if missing else "additional verification"
        return f"I can continue, but I still need: {missing_text}."
    if action in {"approve_refund", "approve_return_and_refund"}:
        return (
            "Your request is approved under policy. "
            f"Issue: {reason}. Refund amount: {amount}."
        )
    return "I need one more detail to proceed with your request."


def build_synthetic_example(case: dict[str, Any]) -> dict[str, str]:
    extracted = case.get("extracted_fields", {})
    decision = case.get("policy_decision", {})
    reason = case.get("issue_type", "changed_mind")

    prompt = (
        "You are a refund/returns support agent.\n"
        "Given the customer message and context, produce:\n"
        "1) extracted_fields JSON\n"
        "2) tool_plan (ordered list of tool calls)\n"
        "3) customer_reply\n"
        "4) internal_case_summary\n"
        "\n"
        f"customer_message: {case.get('customer_message', '')}\n"
        f"known_fields: {render_json(extracted)}\n"
    )

    completion = {
        "extracted_fields": extracted,
        "tool_plan": [
            {"tool": "lookup_order", "args": {"order_id": extracted.get("order_id")}},
            {
                "tool": "get_policy",
                "args": {
                    "merchant_id": extracted.get("merchant_id"),
                    "item_category": case.get("tool_targets", {})
                    .get("get_policy", {})
                    .get("item_category", "fashion"),
                    "reason": reason,
                    "order_date": extracted.get("order_date"),
                    "delivery_date": extracted.get("delivery_date"),
                },
            },
            {"tool": "check_eligibility", "args": {"reason": reason}},
            {"tool": "compute_refund", "args": {"reason": reason}},
        ],
        "customer_reply": synthesize_customer_reply(decision, reason),
        "internal_case_summary": (
            f"case_id={case.get('case_id')} reason={reason} action={decision.get('next_action')} "
            f"decision_reason={decision.get('decision_reason')}"
        ),
    }

    text = f"<|user|>\n{prompt}\n<|assistant|>\n{render_json(completion)}"
    return {"source": "synthetic_case", "text": text}


def build_tweetsumm_example(row: dict[str, Any]) -> dict[str, str] | None:
    dialog = row.get("dialog", "")
    summary = row.get("summary", "")
    if not summary:
        return None
    prompt = (
        "Summarize the support conversation for internal handoff. Keep it concise and factual.\n"
        f"dialog: {dialog}"
    )
    completion = {"internal_case_summary": summary}
    text = f"<|user|>\n{prompt}\n<|assistant|>\n{render_json(completion)}"
    return {"source": "tweetsumm", "text": text}


def build_sft_records(
    synthetic_cases: list[dict[str, Any]],
    tweetsumm_rows: list[dict[str, Any]],
    conversation_rows: list[dict[str, str]],
    max_synthetic: int | None,
    max_tweetsumm: int | None,
    max_conversation: int | None,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    for case in synthetic_cases[: max_synthetic or len(synthetic_cases)]:
        records.append(build_synthetic_example(case))

    used = 0
    for row in tweetsumm_rows:
        if max_tweetsumm is not None and used >= max_tweetsumm:
            break
        ex = build_tweetsumm_example(row)
        if ex is None:
            continue
        records.append(ex)
        used += 1

    records.extend(conversation_rows[: max_conversation or len(conversation_rows)])

    return records


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def run_training(
    model_id: str,
    train_rows: list[dict[str, str]],
    val_rows: list[dict[str, str]],
    output_dir: Path,
    batch_size: int,
    grad_accum: int,
    learning_rate: float,
    num_epochs: float,
    max_seq_len: int,
    lora_r: int,
    lora_alpha: int,
    lora_dropout: float,
) -> None:
    from packaging.version import parse as vparse
    import accelerate
    import transformers
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from trl import SFTTrainer

    if vparse(transformers.__version__) >= vparse("4.56.0") and vparse(accelerate.__version__) < vparse("1.0.0"):
        raise RuntimeError(
            "Incompatible library versions detected: transformers>=4.56 requires newer accelerate for Trainer runtime. "
            "Run: pip install -U 'accelerate>=1.0.0' and restart runtime."
        )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "QLoRA training requires CUDA GPU in this script. Use --prepare-only on CPU/macOS or run on a CUDA host."
        )

    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="auto",
    )

    peft_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    train_ds = Dataset.from_list(train_rows)
    eval_ds = Dataset.from_list(val_rows) if val_rows else None

    arg_kwargs = {
        "output_dir": str(output_dir),
        "per_device_train_batch_size": batch_size,
        "per_device_eval_batch_size": batch_size,
        "gradient_accumulation_steps": grad_accum,
        "learning_rate": learning_rate,
        "num_train_epochs": num_epochs,
        "bf16": torch.cuda.is_bf16_supported(),
        "fp16": not torch.cuda.is_bf16_supported(),
        "logging_steps": 10,
        "save_steps": 200,
        "eval_steps": 200 if eval_ds is not None else None,
        "save_total_limit": 2,
        "report_to": [],
        "gradient_checkpointing": True,
    }
    ta_sig = inspect.signature(TrainingArguments.__init__)
    strategy_value = "steps" if eval_ds is not None else "no"
    if "evaluation_strategy" in ta_sig.parameters:
        arg_kwargs["evaluation_strategy"] = strategy_value
    elif "eval_strategy" in ta_sig.parameters:
        arg_kwargs["eval_strategy"] = strategy_value

    args = TrainingArguments(**arg_kwargs)

    sft_kwargs: dict[str, Any] = {
        "model": model,
        "train_dataset": train_ds,
        "eval_dataset": eval_ds,
        "peft_config": peft_config,
        "args": args,
    }
    sft_sig = inspect.signature(SFTTrainer.__init__)

    if "tokenizer" in sft_sig.parameters:
        sft_kwargs["tokenizer"] = tokenizer
    elif "processing_class" in sft_sig.parameters:
        sft_kwargs["processing_class"] = tokenizer

    if "dataset_text_field" in sft_sig.parameters:
        sft_kwargs["dataset_text_field"] = "text"
    elif "formatting_func" in sft_sig.parameters:
        sft_kwargs["formatting_func"] = lambda example: example["text"]

    if "max_seq_length" in sft_sig.parameters:
        sft_kwargs["max_seq_length"] = max_seq_len

    trainer = SFTTrainer(**sft_kwargs)

    trainer.train()
    trainer.save_model(str(output_dir / "adapter"))
    tokenizer.save_pretrained(str(output_dir / "adapter"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SFT QLoRA trainer for refund-returns-agent")
    parser.add_argument("--model", default="mistral-7b-instruct-v0.2", help="Preset name or HF model id")
    parser.add_argument("--train-cases", type=Path, default=Path("data/processed/synthetic_cases_train.jsonl"))
    parser.add_argument("--val-cases", type=Path, default=Path("data/processed/synthetic_cases_val.jsonl"))
    parser.add_argument("--tweetsumm", type=Path, default=Path("data/processed/tweetsumm_pairs.jsonl"))
    parser.add_argument(
        "--conversation-records-train",
        type=Path,
        default=Path("data/processed/conversation_sft_train.jsonl"),
    )
    parser.add_argument(
        "--conversation-records-val",
        type=Path,
        default=Path("data/processed/conversation_sft_val.jsonl"),
    )
    parser.add_argument("--prepared-train", type=Path, default=Path("data/processed/sft_train_prepared.jsonl"))
    parser.add_argument("--prepared-val", type=Path, default=Path("data/processed/sft_val_prepared.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/sft_qlora"))
    parser.add_argument("--max-synthetic-train", type=int, default=6000)
    parser.add_argument("--max-tweetsumm-train", type=int, default=2000)
    parser.add_argument("--max-synthetic-val", type=int, default=1000)
    parser.add_argument("--max-tweetsumm-val", type=int, default=200)
    parser.add_argument("--max-conversation-train", type=int, default=3000)
    parser.add_argument("--max-conversation-val", type=int, default=500)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--num-epochs", type=float, default=1.0)
    parser.add_argument("--max-seq-len", type=int, default=1024)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    return parser.parse_args()


def resolve_model(model_arg: str) -> str:
    return MODEL_PRESETS.get(model_arg, model_arg)


def main() -> None:
    args = parse_args()

    train_cases = load_jsonl(args.train_cases, limit=args.max_synthetic_train)
    val_cases = load_jsonl(args.val_cases, limit=args.max_synthetic_val)
    tweetsumm_rows = load_jsonl(args.tweetsumm)
    conversation_train_rows = load_text_records(
        args.conversation_records_train,
        limit=args.max_conversation_train,
    )
    conversation_val_rows = load_text_records(
        args.conversation_records_val,
        limit=args.max_conversation_val,
    )

    train_rows = build_sft_records(
        train_cases,
        tweetsumm_rows,
        conversation_train_rows,
        max_synthetic=args.max_synthetic_train,
        max_tweetsumm=args.max_tweetsumm_train,
        max_conversation=args.max_conversation_train,
    )
    val_rows = build_sft_records(
        val_cases,
        tweetsumm_rows,
        conversation_val_rows,
        max_synthetic=args.max_synthetic_val,
        max_tweetsumm=args.max_tweetsumm_val,
        max_conversation=args.max_conversation_val,
    )

    write_jsonl(args.prepared_train, train_rows)
    write_jsonl(args.prepared_val, val_rows)

    model_id = resolve_model(args.model)

    summary = {
        "model": model_id,
        "prepared_train_rows": len(train_rows),
        "prepared_val_rows": len(val_rows),
        "prepared_train_path": str(args.prepared_train),
        "prepared_val_path": str(args.prepared_val),
        "prepare_only": args.prepare_only,
    }

    if args.prepare_only:
        print(json.dumps(summary, ensure_ascii=True))
        return

    run_training(
        model_id=model_id,
        train_rows=train_rows,
        val_rows=val_rows,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        learning_rate=args.learning_rate,
        num_epochs=args.num_epochs,
        max_seq_len=args.max_seq_len,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
    )
    summary["output_dir"] = str(args.output_dir)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
