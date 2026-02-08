from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ship_ready_gate import check


def test_check_missing_files(tmp_path: Path):
    out = check(tmp_path, max_age_hours=1.0)
    assert out["ok"] is False
    assert out["present_count"] == 0
    assert len(out["missing"]) > 0
