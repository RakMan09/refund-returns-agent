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


def merge_pair_sources(
    base_pairs: list[dict[str, Any]],
    conversation_pairs: list[dict[str, Any]],
    max_base: int | None,
    max_conversation: int | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    merged.extend(base_pairs[: max_base or len(base_pairs)])
    merged.extend(conversation_pairs[: max_conversation or len(conversation_pairs)])
    return merged


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def to_chat_record(pair: dict[str, Any]) -> dict[str, str]:
    prompt = str(pair.get("prompt", ""))
    chosen = pair.get("chosen", {})
    rejected = pair.get("rejected", {})

    prompt_text = (
        "You are a refund/returns support agent. "
        "Choose a safe, policy-compliant action and response.\n"
        f"customer_message: {prompt}"
    )
    return {
        "prompt": f"<|user|>\n{prompt_text}\n<|assistant|>\n",
        "chosen": render_json(chosen),
        "rejected": render_json(rejected),
    }


def prepare_pairs(
    train_pairs: list[dict[str, Any]],
    val_pairs: list[dict[str, Any]],
    max_train: int | None,
    max_val: int | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    train = [to_chat_record(x) for x in train_pairs[: max_train or len(train_pairs)]]
    val = [to_chat_record(x) for x in val_pairs[: max_val or len(val_pairs)]]
    return train, val


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def split_for_val(rows: list[dict[str, Any]], ratio: float = 0.1) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return [], []
    n_val = max(1, int(len(rows) * ratio))
    n_val = min(n_val, len(rows) - 1) if len(rows) > 1 else 0
    if n_val == 0:
        return rows, []
    return rows[:-n_val], rows[-n_val:]


def run_dpo_training(
    *,
    model_id: str,
    adapter_init_dir: Path | None,
    train_rows: list[dict[str, str]],
    val_rows: list[dict[str, str]],
    output_dir: Path,
    batch_size: int,
    grad_accum: int,
    learning_rate: float,
    num_epochs: float,
    max_length: int,
    max_prompt_length: int,
    beta: float,
    lora_r: int,
    lora_alpha: int,
    lora_dropout: float,
) -> None:
    from packaging.version import parse as vparse
    import accelerate
    import transformers
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from trl import DPOTrainer
    try:
        from trl import DPOConfig  # type: ignore
    except Exception:
        DPOConfig = None  # type: ignore

    if not torch.cuda.is_available():
        raise RuntimeError(
            "DPO training in this script requires CUDA GPU. Use --prepare-only on CPU/macOS or run on a CUDA host."
        )
    if vparse(transformers.__version__) >= vparse("4.56.0") and vparse(accelerate.__version__) < vparse("1.0.0"):
        raise RuntimeError(
            "Incompatible library versions detected: transformers>=4.56 requires newer accelerate for Trainer runtime. "
            "Run: pip install -U 'accelerate>=1.0.0' and restart runtime."
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

    # Optional warm-start from SFT adapter weights.
    loaded_existing_adapter = False
    if adapter_init_dir is not None and (adapter_init_dir / "adapter_config.json").exists():
        model = PeftModel.from_pretrained(model, str(adapter_init_dir), is_trainable=True)
        loaded_existing_adapter = True

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

    if DPOConfig is not None:
        dpo_sig = inspect.signature(DPOConfig.__init__)
        dpo_kwargs = dict(arg_kwargs)
        if "beta" in dpo_sig.parameters:
            dpo_kwargs["beta"] = beta
        if "max_length" in dpo_sig.parameters:
            dpo_kwargs["max_length"] = max_length
        if "max_prompt_length" in dpo_sig.parameters:
            dpo_kwargs["max_prompt_length"] = max_prompt_length
        args = DPOConfig(**dpo_kwargs)
    else:
        args = TrainingArguments(**arg_kwargs)
        # Backward/forward compatibility shim for TRL versions expecting DPOConfig attrs.
        for attr, default in [
            ("model_init_kwargs", None),
            ("ref_model_init_kwargs", None),
            ("beta", beta),
            ("max_length", max_length),
            ("max_prompt_length", max_prompt_length),
        ]:
            if not hasattr(args, attr):
                setattr(args, attr, default)

    kwargs: dict[str, Any] = {
        "model": model,
        "args": args,
        "train_dataset": train_ds,
        "eval_dataset": eval_ds,
    }

    sig = inspect.signature(DPOTrainer.__init__)
    if "tokenizer" in sig.parameters:
        kwargs["tokenizer"] = tokenizer
    elif "processing_class" in sig.parameters:
        kwargs["processing_class"] = tokenizer

    if "beta" in sig.parameters:
        kwargs["beta"] = beta
    if "max_length" in sig.parameters:
        kwargs["max_length"] = max_length
    if "max_prompt_length" in sig.parameters:
        kwargs["max_prompt_length"] = max_prompt_length
    # TRL rejects passing peft_config when model is already a PeftModel.
    if "peft_config" in sig.parameters and not loaded_existing_adapter:
        kwargs["peft_config"] = peft_config
    if "ref_model" in sig.parameters:
        kwargs["ref_model"] = None

    trainer = DPOTrainer(**kwargs)
    trainer.train()
    trainer.save_model(str(output_dir / "adapter"))
    tokenizer.save_pretrained(str(output_dir / "adapter"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DPO trainer for policyLLM-support-bot")
    parser.add_argument("--model", default="mistral-7b-instruct-v0.2", help="Preset name or HF model id")
    parser.add_argument(
        "--train-pairs", type=Path, default=Path("data/processed/dpo_pairs_train.jsonl"), help="Raw DPO pairs"
    )
    parser.add_argument(
        "--conversation-train-pairs",
        type=Path,
        default=Path("data/processed/conversation_dpo_pairs_train.jsonl"),
        help="Conversation DPO preference pairs",
    )
    parser.add_argument(
        "--val-pairs", type=Path, default=None, help="Optional val pairs path; split train if omitted"
    )
    parser.add_argument("--prepared-train", type=Path, default=Path("data/processed/dpo_train_prepared.jsonl"))
    parser.add_argument("--prepared-val", type=Path, default=Path("data/processed/dpo_val_prepared.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/dpo_qlora"))
    parser.add_argument("--adapter-init-dir", type=Path, default=Path("models/sft_qlora/adapter"))
    parser.add_argument("--max-train", type=int, default=5000)
    parser.add_argument("--max-val", type=int, default=500)
    parser.add_argument("--max-conversation-train", type=int, default=3000)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=5e-6)
    parser.add_argument("--num-epochs", type=float, default=1.0)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--max-prompt-length", type=int, default=512)
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    return parser.parse_args()


def resolve_model(model_arg: str) -> str:
    return MODEL_PRESETS.get(model_arg, model_arg)


def main() -> None:
    args = parse_args()

    base_train = load_jsonl(args.train_pairs)
    conversation_train = load_jsonl(
        args.conversation_train_pairs,
        limit=args.max_conversation_train,
    )
    raw_train = merge_pair_sources(
        base_train,
        conversation_train,
        max_base=args.max_train,
        max_conversation=args.max_conversation_train,
    )
    if args.val_pairs is not None:
        raw_val = load_jsonl(args.val_pairs)
    else:
        raw_train, raw_val = split_for_val(raw_train, ratio=0.1)

    train_rows, val_rows = prepare_pairs(
        raw_train,
        raw_val,
        max_train=args.max_train,
        max_val=args.max_val,
    )
    write_jsonl(args.prepared_train, train_rows)
    write_jsonl(args.prepared_val, val_rows)

    model_id = resolve_model(args.model)

    summary = {
        "model": model_id,
        "base_pairs": len(base_train),
        "conversation_pairs": len(conversation_train),
        "merged_pairs": len(raw_train) + len(raw_val),
        "prepared_train_rows": len(train_rows),
        "prepared_val_rows": len(val_rows),
        "prepared_train_path": str(args.prepared_train),
        "prepared_val_path": str(args.prepared_val),
        "prepare_only": args.prepare_only,
    }
    if args.prepare_only:
        print(json.dumps(summary, ensure_ascii=True))
        return

    run_dpo_training(
        model_id=model_id,
        adapter_init_dir=args.adapter_init_dir,
        train_rows=train_rows,
        val_rows=val_rows,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        learning_rate=args.learning_rate,
        num_epochs=args.num_epochs,
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
        beta=args.beta,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
    )
    summary["output_dir"] = str(args.output_dir)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
