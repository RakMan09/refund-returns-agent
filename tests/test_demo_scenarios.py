from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.demo_scenarios import _first_option


def test_first_option_returns_value():
    response = {
        "controls": [
            {
                "field": "selected_order_id",
                "options": [{"label": "ORD-1", "value": "ORD-1"}],
            }
        ]
    }
    assert _first_option(response, "selected_order_id") == "ORD-1"
