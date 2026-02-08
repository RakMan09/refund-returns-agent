from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from services.agent_server.app.chat_flow import ChatFlowManager
from services.agent_server.app.config import settings
from services.agent_server.app.orchestrator import AgentOrchestrator
from services.agent_server.app.schemas import (
    AgentRequest,
    AgentResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatStartRequest,
    ChatStartResponse,
    CreateTestOrderRequest,
    CreateTestOrderResponse,
)
from services.agent_server.app.tool_client import ToolClient

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("agent_server")

app = FastAPI(title="refund-returns-agent-server")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/respond", response_model=AgentResponse)
def respond(request: AgentRequest) -> AgentResponse:
    tools = ToolClient(settings.tool_server_url)
    orchestrator = AgentOrchestrator(tools)
    response = orchestrator.run(request)
    logger.info("agent_decision case_id=%s action=%s", request.case_id, response.final_action)
    return response


@app.post("/chat/start", response_model=ChatStartResponse)
def chat_start(request: ChatStartRequest) -> ChatStartResponse:
    tools = ToolClient(settings.tool_server_url)
    flow = ChatFlowManager(tools)
    return flow.start(request)


@app.post("/chat/message", response_model=ChatMessageResponse)
def chat_message(request: ChatMessageRequest) -> ChatMessageResponse:
    if "<" in request.session_id or ">" in request.session_id:
        raise HTTPException(status_code=422, detail="invalid_session_id")
    tools = ToolClient(settings.tool_server_url)
    flow = ChatFlowManager(tools)
    try:
        return flow.message(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"chat_message_failed: {exc}") from exc


@app.post("/chat/create_test_order", response_model=CreateTestOrderResponse)
def create_test_order(request: CreateTestOrderRequest) -> CreateTestOrderResponse:
    tools = ToolClient(settings.tool_server_url)
    out = tools.create_test_order(request.model_dump(mode="json"))
    return CreateTestOrderResponse(order_id=out["order_id"])
