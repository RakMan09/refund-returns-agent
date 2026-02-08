from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

REQUIRED_PATHS = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".gitignore",
    ".env.example",
    "docker-compose.yml",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    "services/tool_server/app/main.py",
    "services/agent_server/app/main.py",
    "services/ui/app.py",
    "eval/eval_harness.py",
    "eval/conversation_eval.py",
    "eval/safety_suite.py",
    "training/sft_train.py",
    "training/dpo_train.py",
    "pipelines/build_dataset.py",
    "pipelines/build_conversation_dataset.py",
]

SECRET_PATTERNS = [
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_api_key", re.compile(r"(?i)api[_-]?key\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def scan_text_for_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(name)
    return hits


def tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def is_probably_binary(path: Path) -> bool:
    try:
        blob = path.read_bytes()[:2048]
    except Exception:
        return True
    if b"\x00" in blob:
        return True
    return False


def run_audit(repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_PATHS:
        if not (repo_root / rel).exists():
            errors.append(f"missing_required_path:{rel}")

    # Ensure .env is not tracked.
    tracked = tracked_files()
    if ".env" in tracked:
        errors.append("tracked_secret_file:.env")

    # Secret scan on tracked text files.
    secret_hits: list[dict[str, Any]] = []
    for rel in tracked:
        path = repo_root / rel
        if not path.exists() or not path.is_file():
            continue
        if is_probably_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        hits = scan_text_for_secrets(text)
        if hits:
            secret_hits.append({"path": rel, "patterns": hits})

    if secret_hits:
        errors.append("secret_like_patterns_detected")

    if not (repo_root / "data/raw/.gitkeep").exists():
        warnings.append("missing_placeholder:data/raw/.gitkeep")
    if not (repo_root / "data/processed/.gitkeep").exists():
        warnings.append("missing_placeholder:data/processed/.gitkeep")
    if not (repo_root / "data/evidence/.gitkeep").exists():
        warnings.append("missing_placeholder:data/evidence/.gitkeep")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "secret_hits": secret_hits,
        "tracked_files_count": len(tracked),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Final repository audit before GitHub publish.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("eval/results/final_audit_report.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_audit(args.repo_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "output": str(args.output)}, ensure_ascii=True))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
