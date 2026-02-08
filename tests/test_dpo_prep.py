from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dpo_train import merge_pair_sources, prepare_pairs, split_for_val, to_chat_record


def test_to_chat_record_shape():
    pair = {
        "prompt": "item is damaged",
        "chosen": {"action": "request_info", "reason": "need photo"},
        "rejected": {"action": "approve_refund", "reason": "ignored policy"},
    }
    row = to_chat_record(pair)
    assert set(row.keys()) == {"prompt", "chosen", "rejected"}
    assert "<|user|>" in row["prompt"]
    assert "<|assistant|>" in row["prompt"]


def test_split_for_val_non_empty():
    rows = [{"i": i} for i in range(10)]
    train, val = split_for_val(rows, ratio=0.2)
    assert len(train) == 8
    assert len(val) == 2


def test_prepare_pairs_limits():
    train_pairs = [{"prompt": "a", "chosen": {"x": 1}, "rejected": {"x": 0}} for _ in range(5)]
    val_pairs = [{"prompt": "b", "chosen": {"x": 1}, "rejected": {"x": 0}} for _ in range(4)]
    train, val = prepare_pairs(train_pairs, val_pairs, max_train=3, max_val=2)
    assert len(train) == 3
    assert len(val) == 2


def test_merge_pair_sources_limits():
    base = [{"prompt": "a", "chosen": {"x": 1}, "rejected": {"x": 0}} for _ in range(5)]
    conv = [{"prompt": "b", "chosen": {"x": 1}, "rejected": {"x": 0}} for _ in range(4)]
    merged = merge_pair_sources(base, conv, max_base=3, max_conversation=2)
    assert len(merged) == 5
