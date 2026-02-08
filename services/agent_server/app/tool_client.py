from __future__ import annotations

from typing import Any

import httpx


class ToolClient:
    """Allowlisted, schema-constrained tool client."""

    def __init__(self, base_url: str, timeout_s: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            response = client.post(f"{self.base_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()

    def lookup_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/lookup_order", payload)

    def list_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/list_orders", payload)

    def list_order_items(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/list_order_items", payload)

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/create_session", payload)

    def get_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/get_session", payload)

    def set_selected_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/set_selected_order", payload)

    def set_selected_items(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/set_selected_items", payload)

    def update_session_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/update_session_state", payload)

    def append_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/append_chat_message", payload)

    def get_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/get_policy", payload)

    def check_eligibility(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/check_eligibility", payload)

    def compute_refund(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/compute_refund", payload)

    def create_return(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/create_return", payload)

    def create_label(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/create_label", payload)

    def create_escalation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/create_escalation", payload)

    def create_test_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/create_test_order", payload)

    def get_case_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/get_case_status", payload)

    def upload_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/upload_evidence", payload)

    def get_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/get_evidence", payload)

    def validate_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tools/validate_evidence", payload)
