from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_FILES = [
    "docs/METRICS.md",
    "docs/RELEASE_SUMMARY.md",
    "docs/RELEASE_NOTES.md",
    "docs/PORTFOLIO_REPORT.md",
    "eval/results/eval_report.json",
    "eval/results/conversation_eval_report.json",
    "eval/results/safety_report.json",
    "eval/results/final_audit_report.json",
    "eval/results/demo_scenarios.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(repo_root: Path, rel_paths: list[str]) -> dict:
    files: list[dict] = []
    missing: list[str] = []
    for rel in rel_paths:
        p = repo_root / rel
        if not p.exists():
            missing.append(rel)
            continue
        files.append(
            {
                "path": rel,
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
        )
    return {"files": files, "missing": missing, "count": len(files)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate artifact manifest with SHA256 hashes.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("dist/release_manifest.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    manifest = build_manifest(repo_root, DEFAULT_FILES)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "count": manifest["count"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
