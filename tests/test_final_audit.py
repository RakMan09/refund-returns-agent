from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.final_audit import scan_text_for_secrets


def test_secret_scan_detects_openai_style_key():
    text = "OPENAI_API_KEY=sk-1234567890abcdef1234567890abcdef"
    hits = scan_text_for_secrets(text)
    assert "openai_key" in hits


def test_secret_scan_ignores_safe_text():
    text = "customer_email_masked=al***@example.com"
    hits = scan_text_for_secrets(text)
    assert hits == []
