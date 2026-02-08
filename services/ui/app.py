from __future__ import annotations

import base64
import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st

AGENT_URL = os.getenv("AGENT_SERVER_URL", "http://localhost:8002")

st.set_page_config(page_title="Refund Returns Chatbot", layout="wide")
st.title("Refund Returns Chatbot")
st.caption("Stateful multi-turn support flow with guided controls")
st.markdown(
    """
    <style>
    .stApp {background: linear-gradient(180deg, #f7f9fc 0%, #eef3f8 100%);}
    [data-testid="stSidebar"] {background: #ffffff;}
    .stChatMessage {border-radius: 12px;}
    </style>
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
        st.session_state["messages"] = [
            {"role": "assistant", "content": chat["assistant_message"]}
        ]
        st.session_state["controls"] = chat.get("controls", [])
        st.session_state["timeline"] = []

    st.markdown("---")
    st.subheader("Create Test Order")
    test_email = st.text_input("Customer Email", "demo@example.com")
    test_phone = st.text_input("Phone last 4", "1111")
    test_product = st.text_input("Product", "Demo Product")
    test_qty = st.number_input("Quantity", min_value=1, max_value=20, value=1)
    test_category = st.selectbox("Category", ["electronics", "fashion", "apparel", "home"])
    test_price = st.number_input("Price", min_value=1.0, value=59.99)
    test_ship = st.number_input("Shipping Fee", min_value=0.0, value=5.0)
    test_status = st.selectbox("Status", ["processing", "shipped", "delivered"])

    if st.button("Create Test Order", use_container_width=True):
        payload = {
            "customer_email": test_email,
            "customer_phone_last4": test_phone,
            "product_name": test_product,
            "quantity": int(test_qty),
            "item_category": test_category,
            "price": str(test_price),
            "shipping_fee": str(test_ship),
            "status": test_status,
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

    with st.chat_message("user"):
        free = st.text_input("Free chat message", key="free_chat")
        if st.button("Send message") and free.strip():
            st.session_state["messages"].append({"role": "user", "content": free})
            send_chat({"session_id": st.session_state["session_id"], "text": free})
            st.rerun()

with right:
    st.subheader("Case Status")
    st.write(f"Session: `{st.session_state.get('session_id')}`")
    st.write(f"Case: `{st.session_state.get('case_id')}`")

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

    st.subheader("Timeline")
    timeline = st.session_state.get("timeline", [])
    if timeline:
        st.dataframe(pd.DataFrame(timeline), use_container_width=True)
    else:
        st.info("No timeline events yet.")
