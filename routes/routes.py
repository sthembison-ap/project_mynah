from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas.context import InteractionRequest, InteractionResponse, AccountSnapshot
from orchestration.flow import OrchestrationRequest, run_orchestration

import json #Importing this here just for TESTING Context dump
import uuid

from agents.master import MasterAgent
from agents.nlu import NLUAgent
from agents.data_agent import DataAgent
from orchestration.flow import build_initial_context

import os
import time

from services.session_store import SessionStore

router = APIRouter(tags=["interaction"])

# Initialize session store for Redis monitoring
session_store = SessionStore()

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
    agent_response, nlu_agent_response, orchestration_response = await run_orchestration(request)

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
    agent_response, nlu_agent_response, orchestration_response = await run_orchestration(request)

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

@agents_router.post("/data/run")
async def run_data_agent(request: OrchestrationRequest):
    """
    Fetch account information using the Data Agent.
    
    The message should contain a 13-digit SA ID number.
    """
    context = build_initial_context(request)
    agent = DataAgent()

    # Extract ID number from message (assume the message IS the ID number)
    id_number = request.message.strip().replace(" ", "").replace("-", "")

    # Validate ID number format
    if not id_number.isdigit() or len(id_number) != 13:
        return {
            "session_id": context.session_id,
            "debtor_id": context.debtor_id,
            "success": False,
            "error_message": "Please provide a valid 13-digit South African ID number.",
            "matter_details": None,
            "agent_path": ["DataAgent"],
        }

    # Run the data agent
    context = await agent.run_async(context, id_number)

    # Return the result
    return {
        "session_id": context.session_id,
        "debtor_id": context.debtor_id,
        "success": context.understood_message,
        "matter_details": context.matter_details.model_dump() if context.matter_details else None,
        "error_message": None if context.understood_message else "Failed to fetch account information.",
        "agent_path": context.agent_path,
        "response": context.final_response,
    }


# Include the agents router with the /api/v1 prefix
router.include_router(agents_router, prefix="/api/v1/agents")


# ---------- Redis Monitoring Endpoints ----------
redis_router = APIRouter(prefix="/redis", tags=["redis-monitor"])


@redis_router.get("/health")
async def redis_health():
    """Check Redis connection health."""
    try:
        start = time.time()

        if session_store.is_redis:
            session_store.redis_client.ping()
            latency = (time.time() - start) * 1000

            return {
                "status": "connected",
                "backend": "redis",
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", 6379)),
                "latency_ms": round(latency, 2)
            }
        else:
            return {
                "status": "connected",
                "backend": "in-memory",
                "host": "localhost",
                "latency_ms": 0
            }
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


@redis_router.get("/stats")
async def redis_stats():
    """Get Redis/session store statistics."""
    return session_store.get_stats()


@redis_router.get("/sessions")
async def list_sessions(search: str = None, limit: int = 100):
    """List all active sessions."""
    sessions = session_store.list_sessions(search=search)

    return {
        "total": len(sessions),
        "sessions": sessions[:limit]
    }


@redis_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get full session details."""
    data = session_store.load(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")

    ttl = session_store.get_ttl(session_id)

    return {
        "session_id": session_id,
        "ttl_seconds": ttl,
        "data": data
    }


@redis_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session."""
    if not session_store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    success = session_store.delete(session_id)
    return {"success": success, "message": "Session deleted" if success else "Failed to delete"}


class ClearSessionsRequest(BaseModel):
    confirm: bool = False


@redis_router.post("/sessions/clear")
async def clear_all_sessions(request: ClearSessionsRequest):
    """Clear all sessions (requires confirmation)."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set 'confirm': true to proceed."
        )

    deleted_count = session_store.clear_all_sessions()
    return {"success": True, "deleted_count": deleted_count}


# Include the redis router with the /api/v1 prefix
router.include_router(redis_router)