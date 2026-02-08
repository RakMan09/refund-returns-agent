from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_release_bundle import build_bundle, build_release_summary


def test_build_release_summary_contains_metrics():
    eval_report = {"metrics": {"decision_accuracy": 0.3, "tool_validity_rate": 1.0}}
    conv_report = {"metrics": {"task_success_rate": 0.8}}
    safety_report = {"summary": {"pass_rate": 0.9}}
    text = build_release_summary(eval_report, conv_report, safety_report)
    assert "offline.decision_accuracy: 0.3" in text
    assert "conversation.task_success_rate: 0.8" in text
    assert "safety.pass_rate: 0.9" in text


def test_build_bundle_includes_existing_and_reports_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("ok", encoding="utf-8")
    out = build_bundle(repo, tmp_path / "dist", ["README.md", "missing.txt"])
    assert Path(out["bundle_path"]).exists()
    assert "README.md" in out["included_files"]
    assert "missing.txt" in out["missing_files"]
