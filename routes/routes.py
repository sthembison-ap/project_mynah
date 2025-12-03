from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas.context import InteractionRequest, InteractionResponse, AccountSnapshot
from orchestration.flow import OrchestrationRequest, run_orchestration

import json #Importing this here just for TESTING Context dump
import uuid

from agents.master import MasterAgent
from agents.nlu import NLUAgent
from orchestration.flow import build_initial_context

router = APIRouter(tags=["interaction"])

# ---------- Chat UI Endpoint ----------
class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None
    debtor_id: str | None = None


@router.post("/chat")
async def chat(chat_msg: ChatMessage):
    """
    Chat endpoint for the UI - triggers orchestration and returns a response.
    """
    # Generate session/debtor IDs if not provided
    session_id = chat_msg.session_id or f"session_{uuid.uuid4().hex[:12]}"
    debtor_id = chat_msg.debtor_id or "guest_user"

    # Create orchestration request
    request = OrchestrationRequest(
        message=chat_msg.message,
        session_id=session_id,
        debtor_id=debtor_id,
        channel="webchat"
    )

    # Run orchestration
    agent_response, nlu_agent_response, orchestration_response = run_orchestration(request)

    # Return the response for the chat UI
    return {
        "response": orchestration_response.response,
        "session_id": session_id,
        "intent": getattr(orchestration_response, "intent", None),
        "entities": nlu_agent_response.Entities if hasattr(nlu_agent_response, "Entities") else None,
        "status": orchestration_response.status
    }

@router.post("/orchestrate")
async def orchestrate(request: OrchestrationRequest):
    agent_response, nlu_agent_response, orchestration_response = run_orchestration(request)

    return {
        "agent_response": agent_response,
        "nlu_agent_response": nlu_agent_response,
        "orchestration_response": orchestration_response
    }


# ---------- Health Check API ----------
@router.get("/health")
async def health_check():
    """
    Health & uptime check endpoint.
    """
    return {"status": "healthy", "message": "Service is running"}


# ---------- Internal Agent Endpoints (For Testing Purposes ONLY [NEVER TO BE RUN IN ISOLATION DURING PRODUCTION] ----------
agents_router = APIRouter(tags=["agents"])

@agents_router.post("/master/run")
async def run_master_agent(request: OrchestrationRequest):
    """
    Classify message intent using the Master Agent.
    """
    context = build_initial_context(request)
    agent = MasterAgent()
    agent_result = agent.run(context)

    return {
        "session_id": context.session_id,
        "debtor_id": context.debtor_id,
        "intent": context.intent,
        "understood_message": context.understood_message,
        "agent_path": context.agent_path,
        "reasoning": getattr(context, "reasoning", None),
    }


@agents_router.post("/nlu/run")
async def run_nlu_agent(request: OrchestrationRequest):
    """
    Extract entities using the NLU Agent.
    """
    context = build_initial_context(request)
    agent = NLUAgent()
    nlu_result = agent.run(context)

    return {
        "session_id": context.session_id,
        "debtor_id": context.debtor_id,
        "entities": nlu_result.entities if hasattr(nlu_result, "entities") else context.entities,
        "nlu_reasoning": getattr(context, "nlu_reasoning", None),
        "agent_path": context.agent_path,
    }


# Include the agents router with the /api/v1 prefix
router.include_router(agents_router, prefix="/api/v1/agents")