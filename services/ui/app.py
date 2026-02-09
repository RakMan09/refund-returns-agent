from __future__ import annotations

import base64
import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st

AGENT_URL = os.getenv("AGENT_SERVER_URL", "http://localhost:8002")
STATUS_COLORS = {
    "Awaiting User Info": "#3a86ff",
    "Awaiting User Choice": "#2a9d8f",
    "Awaiting Evidence": "#f4a261",
    "Refund Pending": "#1d3557",
    "Return Pending": "#1d3557",
    "Replacement Pending": "#1d3557",
    "Resolved": "#2b9348",
    "Escalated": "#c44536",
    "Denied": "#6b7280",
    "Refused": "#6b7280",
    "Status": "#457b9d",
}

st.set_page_config(page_title="policyLLM-support-bot", layout="wide")
st.markdown(
    """
    <style>
    :root {
      --bg-a: #f8fbff;
      --bg-b: #edf3f9;
      --panel: #ffffff;
      --text: #111827;
      --muted: #334155;
      --border: #cfd8e3;
    }
    .stApp {
      background: radial-gradient(circle at 12% 12%, #ffffff 0%, var(--bg-a) 42%, var(--bg-b) 100%);
      color: var(--text);
    }
    [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      border-right: 1px solid var(--border);
      color: var(--text);
    }
    .hero {
      background: linear-gradient(120deg, #264653 0%, #457b9d 52%, #2a9d8f 100%);
      color: white;
      border-radius: 14px;
      padding: 16px 18px;
      margin-bottom: 10px;
      box-shadow: 0 6px 18px rgba(15, 23, 42, 0.15);
    }
    .hero h1 {
      margin: 0;
      font-size: 1.5rem;
      letter-spacing: 0.2px;
    }
    .hero p {
      margin: 6px 0 0 0;
      color: #e3f2fd;
      font-size: 0.95rem;
    }
    .info-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      margin-bottom: 10px;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
      color: var(--text);
    }
    .status-chip {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      color: white;
      font-size: 0.82rem;
      font-weight: 600;
      margin-top: 8px;
    }
    .timeline-wrap {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 8px;
      color: var(--text);
    }
    .stChatMessage {
      border-radius: 12px;
      border: 1px solid var(--border);
      background: #ffffff;
      color: var(--text);
    }
    .control-box {
      background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
      border: 1px dashed var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      margin: 8px 0;
      color: var(--text);
    }
    .stButton > button {
      background: #eef4fa !important;
      color: #111827 !important;
      border: 1px solid #cfd8e3 !important;
    }
    .stButton > button:hover {
      background: #e4edf7 !important;
      color: #0f172a !important;
    }
    [data-baseweb=\"select\"] > div {
      background: #f8fbff !important;
      color: #111827 !important;
    }
    .stTextInput input,
    .stNumberInput input,
    div[data-baseweb=\"input\"] input,
    div[data-baseweb=\"textarea\"] textarea,
    input,
    textarea {
      background: #ffffff !important;
      color: #111827 !important;
      border: 1px solid #cfd8e3 !important;
    }
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    textarea::placeholder {
      color: #475569 !important;
      opacity: 1 !important;
    }
    .stDataFrame, .stDataEditor {
      background: #ffffff !important;
      color: #111827 !important;
    }
    .stTextInput label, .stNumberInput label, .stSelectbox label {
      color: var(--text) !important;
      font-weight: 600;
    }
    .stMarkdown, .stCaption, p, span, div {
      color: var(--text);
    }
    code, pre {
      color: #0f172a !important;
      background: #f1f5f9 !important;
      border: 1px solid #cfd8e3;
      border-radius: 6px;
      padding: 2px 6px;
    }
    .info-card code {
      color: #0f172a !important;
      background: #f8fbff !important;
      border: 1px solid #cfd8e3 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="hero">
      <h1>policyLLM-support-bot</h1>
      <p>Stateful multi-turn support with policy-grounded decisions, evidence flow, and timeline tracing.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("Settings")
    agent_url = st.text_input("Agent URL", AGENT_URL)
    if st.button("Start New Chat", use_container_width=True):
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{agent_url.rstrip('/')}/chat/start", json={})
            resp.raise_for_status()
            chat = resp.json()
        st.session_state["session_id"] = chat["session_id"]
        st.session_state["case_id"] = chat["case_id"]
        st.session_state["messages"] = [{"role": "assistant", "content": chat["assistant_message"]}]
        st.session_state["controls"] = chat.get("controls", [])
        st.session_state["timeline"] = []
        st.session_state["status_chip"] = chat.get("status_chip", "Awaiting User Info")

    resume_session_id = st.text_input("Resume Session ID", key="resume_session_id")
    if st.button("Resume Session", use_container_width=True):
        if not resume_session_id.strip():
            st.error("Enter a valid session id.")
        else:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    f"{agent_url.rstrip('/')}/chat/resume",
                    json={"session_id": resume_session_id.strip()},
                )
                resp.raise_for_status()
                chat = resp.json()
            st.session_state["session_id"] = chat["session_id"]
            st.session_state["case_id"] = chat["case_id"]
            st.session_state["messages"] = chat.get("messages", [])
            st.session_state["controls"] = chat.get("controls", [])
            st.session_state["timeline"] = chat.get("timeline", [])
            st.session_state["status_chip"] = chat.get("status_chip", "Status")

    st.markdown("---")
    st.subheader("Model Runtime")
    if st.button("Refresh Model Status", use_container_width=True):
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(f"{agent_url.rstrip('/')}/chat/model/status")
                resp.raise_for_status()
                st.session_state["model_status"] = resp.json()
        except Exception as exc:
            st.session_state["model_status_error"] = str(exc)

    if "model_status" not in st.session_state and "model_status_error" not in st.session_state:
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(f"{agent_url.rstrip('/')}/chat/model/status")
                resp.raise_for_status()
                st.session_state["model_status"] = resp.json()
        except Exception as exc:
            st.session_state["model_status_error"] = str(exc)

    model_status = st.session_state.get("model_status")
    model_status_error = st.session_state.get("model_status_error")
    if model_status:
        ready = bool(model_status.get("ready"))
        enabled = bool(model_status.get("enabled"))
        mode = model_status.get("mode", "N/A")
        st.markdown(
            (
                f"Mode: `{mode}`\n\n"
                f"Enabled: `{enabled}`\n\n"
                f"Ready: `{ready}`\n\n"
                f"Adapter: `{model_status.get('adapter_dir', 'N/A')}`"
            )
        )
        if ready:
            st.success("Model runtime is ready.")
        else:
            missing = model_status.get("missing_artifacts", [])
            st.warning(f"Model not ready. Missing: {missing if missing else 'unknown'}")
    elif model_status_error:
        st.warning(f"Model status unavailable: {model_status_error}")

    st.markdown("---")
    st.subheader("Create Test Order")
    test_email = st.text_input("Customer Email", "demo@example.com")
    test_phone = st.text_input("Phone last 4", "1111")
    test_product = st.text_input("Product", "Demo Product")
    test_qty = st.number_input("Quantity", min_value=1, max_value=20, value=1)
    test_category = st.selectbox("Category", ["electronics", "fashion", "apparel", "home"])
    test_price = st.number_input("Price", min_value=1.0, value=59.99)
    test_ship = st.number_input("Shipping Fee", min_value=0.0, value=5.0)
    st.caption("New test orders are always created with status: delivered")

    if st.button("Create Test Order", use_container_width=True):
        payload = {
            "customer_email": test_email,
            "customer_phone_last4": test_phone,
            "product_name": test_product,
            "quantity": int(test_qty),
            "item_category": test_category,
            "price": str(test_price),
            "shipping_fee": str(test_ship),
            "delivery_date": None,
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(f"{agent_url.rstrip('/')}/chat/create_test_order", json=payload)
                resp.raise_for_status()
                out = resp.json()
            st.success(f"Created order: {out['order_id']}")
        except Exception as exc:
            st.error(f"Failed: {exc}")


def send_chat(payload: dict[str, Any]) -> None:
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(f"{agent_url.rstrip('/')}/chat/message", json=payload)
        resp.raise_for_status()
        out = resp.json()
    st.session_state["messages"].append({"role": "assistant", "content": out["assistant_message"]})
    st.session_state["controls"] = out.get("controls", [])
    st.session_state["timeline"] = out.get("timeline", [])
    st.session_state["status_chip"] = out.get("status_chip", st.session_state.get("status_chip", "Status"))


if "session_id" not in st.session_state:
    st.info("Click 'Start New Chat' in the sidebar to begin.")
    st.stop()

left, right = st.columns([1.8, 1.2], gap="large")

with left:
    st.subheader("Conversation")
    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    controls = st.session_state.get("controls", [])
    for ctrl in controls:
        ctype = ctrl.get("control_type")
        label = ctrl.get("label", "")
        field = ctrl.get("field", "")
        options = ctrl.get("options", [])
        key = f"ctrl_{field}_{ctype}"
        st.markdown("<div class='control-box'>", unsafe_allow_html=True)

        if ctype == "text":
            txt = st.text_input(label, key=key)
            if st.button(f"Send {field}", key=f"btn_{key}") and txt.strip():
                st.session_state["messages"].append({"role": "user", "content": txt})
                send_chat({"session_id": st.session_state["session_id"], "text": txt})
                st.rerun()

        elif ctype == "dropdown":
            labels = [o["label"] for o in options]
            selected = st.selectbox(label, labels, key=key)
            if st.button(f"Choose {field}", key=f"btn_{key}"):
                val = next(o["value"] for o in options if o["label"] == selected)
                st.session_state["messages"].append({"role": "user", "content": f"Selected {val}"})
                send_chat(
                    {
                        "session_id": st.session_state["session_id"],
                        "selected_order_id": val,
                        "text": "",
                    }
                )
                st.rerun()

        elif ctype == "multiselect":
            labels = [o["label"] for o in options]
            selected = st.multiselect(label, labels, key=key)
            if st.button(f"Choose {field}", key=f"btn_{key}") and selected:
                vals = [o["value"] for o in options if o["label"] in selected]
                st.session_state["messages"].append({"role": "user", "content": f"Selected {vals}"})
                send_chat(
                    {
                        "session_id": st.session_state["session_id"],
                        "selected_item_ids": vals,
                        "text": "",
                    }
                )
                st.rerun()

        elif ctype == "buttons":
            st.write(label)
            cols = st.columns(max(1, len(options)))
            for i, opt in enumerate(options):
                if cols[i].button(opt["label"], key=f"btn_{key}_{i}"):
                    payload = {"session_id": st.session_state["session_id"], "text": ""}
                    if field == "satisfaction":
                        payload["satisfaction"] = opt["value"]
                    elif field == "reason":
                        payload["reason"] = opt["value"]
                    elif field == "preferred_resolution":
                        payload["preferred_resolution"] = opt["value"]
                    st.session_state["messages"].append({"role": "user", "content": opt["label"]})
                    send_chat(payload)
                    st.rerun()

        elif ctype == "file_upload":
            upload = st.file_uploader(label, type=["png", "jpg", "jpeg"], key=key)
            if st.button("Submit evidence", key=f"btn_{key}") and upload is not None:
                file_bytes = upload.getvalue()
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                st.session_state["messages"].append({"role": "user", "content": f"Uploaded {upload.name}"})
                send_chat(
                    {
                        "session_id": st.session_state["session_id"],
                        "evidence_uploaded": True,
                        "evidence_file_name": upload.name,
                        "evidence_mime_type": upload.type or "image/jpeg",
                        "evidence_size_bytes": len(file_bytes),
                        "evidence_content_base64": encoded,
                        "text": "uploaded evidence",
                    }
                )
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    with st.chat_message("user"):
        free = st.text_input("Free chat message", key="free_chat", placeholder="Ask follow-up, status, or end chat")
        if st.button("Send message") and free.strip():
            st.session_state["messages"].append({"role": "user", "content": free})
            send_chat({"session_id": st.session_state["session_id"], "text": free})
            st.rerun()

with right:
    st.subheader("Case Status")
    status_chip = st.session_state.get("status_chip", "Status")
    color = STATUS_COLORS.get(status_chip, "#4361ee")
    st.markdown(
        f"""
        <div class="info-card">
          <div><b>Session</b><br><code>{st.session_state.get('session_id')}</code></div>
          <div style="margin-top:8px;"><b>Case</b><br><code>{st.session_state.get('case_id')}</code></div>
          <div class="status-chip" style="background:{color};">{status_chip}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Refresh Case Status"):
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{agent_url.rstrip('/')}/chat/message",
                json={"session_id": st.session_state["session_id"], "text": "status check"},
            )
            resp.raise_for_status()
            out = resp.json()
        st.session_state["messages"].append({"role": "assistant", "content": out["assistant_message"]})
        st.session_state["timeline"] = out.get("timeline", [])
        st.session_state["status_chip"] = out.get("status_chip", status_chip)

    st.subheader("Timeline")
    timeline = st.session_state.get("timeline", [])
    if timeline:
        st.markdown("<div class='timeline-wrap'>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(timeline), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No timeline events yet.")

    st.subheader("Orders In System")
    if st.button("Refresh Orders Table"):
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{agent_url.rstrip('/')}/chat/orders", params={"limit": 200})
            resp.raise_for_status()
            out = resp.json()
        st.session_state["orders_table"] = out.get("orders", [])

    orders_table = st.session_state.get("orders_table", [])
    if orders_table:
        st.dataframe(pd.DataFrame(orders_table), use_container_width=True, hide_index=True)
    else:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{agent_url.rstrip('/')}/chat/orders", params={"limit": 200})
            resp.raise_for_status()
            out = resp.json()
        st.session_state["orders_table"] = out.get("orders", [])
        if st.session_state["orders_table"]:
            st.dataframe(pd.DataFrame(st.session_state["orders_table"]), use_container_width=True, hide_index=True)
        else:
            st.info("No orders available.")
