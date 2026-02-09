from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from services.agent_server.app.chat_flow import ChatFlowManager
from services.agent_server.app.config import settings
from services.agent_server.app.llm_agent import LLMAdvisor
from services.agent_server.app.llm_runtime import check_llm_runtime_ready
from services.agent_server.app.orchestrator import AgentOrchestrator
from services.agent_server.app.schemas import (
    AgentRequest,
    AgentResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResumeRequest,
    ChatResumeResponse,
    ChatStartRequest,
    ChatStartResponse,
    CreateTestOrderRequest,
    CreateTestOrderResponse,
    ModelStatusResponse,
    OrdersTableResponse,
)
from services.agent_server.app.tool_client import ToolClient

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("agent_server")

app = FastAPI(title="policyllm-support-bot-agent-server")
llm_advisor = LLMAdvisor()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/chat/model/status", response_model=ModelStatusResponse)
def chat_model_status() -> ModelStatusResponse:
    status = check_llm_runtime_ready()
    return ModelStatusResponse(**status.as_dict())


@app.post("/agent/respond", response_model=AgentResponse)
def respond(request: AgentRequest) -> AgentResponse:
    tools = ToolClient(settings.tool_server_url)
    orchestrator = AgentOrchestrator(tools, llm=llm_advisor)
    response = orchestrator.run(request)
    logger.info("agent_decision case_id=%s action=%s", request.case_id, response.final_action)
    return response


@app.post("/chat/start", response_model=ChatStartResponse)
def chat_start(request: ChatStartRequest) -> ChatStartResponse:
    tools = ToolClient(settings.tool_server_url)
    flow = ChatFlowManager(tools, llm=llm_advisor)
    return flow.start(request)


@app.post("/chat/message", response_model=ChatMessageResponse)
def chat_message(request: ChatMessageRequest) -> ChatMessageResponse:
    if "<" in request.session_id or ">" in request.session_id:
        raise HTTPException(status_code=422, detail="invalid_session_id")
    tools = ToolClient(settings.tool_server_url)
    flow = ChatFlowManager(tools, llm=llm_advisor)
    try:
        return flow.message(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"chat_message_failed: {exc}") from exc


@app.post("/chat/resume", response_model=ChatResumeResponse)
def chat_resume(request: ChatResumeRequest) -> ChatResumeResponse:
    if "<" in request.session_id or ">" in request.session_id:
        raise HTTPException(status_code=422, detail="invalid_session_id")
    tools = ToolClient(settings.tool_server_url)
    flow = ChatFlowManager(tools, llm=llm_advisor)
    try:
        return flow.resume(request.session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"chat_resume_failed: {exc}") from exc


@app.post("/chat/create_test_order", response_model=CreateTestOrderResponse)
def create_test_order(request: CreateTestOrderRequest) -> CreateTestOrderResponse:
    tools = ToolClient(settings.tool_server_url)
    out = tools.create_test_order(request.model_dump(mode="json"))
    return CreateTestOrderResponse(order_id=out["order_id"])


@app.get("/chat/orders", response_model=OrdersTableResponse)
def chat_orders(limit: int = 200) -> OrdersTableResponse:
    tools = ToolClient(settings.tool_server_url)
    out = tools.list_all_orders({"limit": limit})
    return OrdersTableResponse(orders=out.get("orders", []))
