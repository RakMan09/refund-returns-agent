from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_manifest import build_manifest


def test_build_manifest_hashes_existing_file(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.txt").write_text("hello", encoding="utf-8")
    out = build_manifest(root, ["a.txt", "missing.txt"])
    assert out["count"] == 1
    assert out["files"][0]["path"] == "a.txt"
    assert len(out["files"][0]["sha256"]) == 64
    assert "missing.txt" in out["missing"]
