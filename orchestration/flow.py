from __future__ import annotations

from typing import Tuple

from schemas.context import ConversationContext, OrchestrationRequest, OrchestrationResponse, AgentResponse, NLUAgentResponse

from agents.master import MasterAgent

from agents.nlu import NLUAgent

import json #Importing this here just for TESTING Context dump
# New imports for intent routing and response generation
from routes.intent_router import IntentRouter
from agents.response_agent import ResponseAgent
from agents.data_agent import DataAgent
from agents.email_agent import EmailAgent

import re
from pydantic import EmailStr, ValidationError

import logging

# Session state management
from services.session_store import SessionStore


logger = logging.getLogger(__name__)

# Initialize session store (singleton pattern)
session_store = SessionStore(ttl_seconds=3600)  # 1 hour session timeout

def build_initial_context(request: OrchestrationRequest) -> ConversationContext:
    return ConversationContext(
        session_id=request.session_id, 
        debtor_id=request.debtor_id,
        last_user_message=request.message,
    )

def is_id_number(message: str) -> bool:
    """Check if the message looks like a South African ID number (13 digits)."""
    cleaned = message.strip().replace(" ", "").replace("-", "")
    return bool(re.match(r'^\d{13}$', cleaned))

def is_email(message: str) -> bool:
    """Check if the message looks like a valid email address."""
    message = message.strip()

    # Quick pre-check: must contain @ and no spaces (emails don't have spaces)
    if '@' not in message or ' ' in message:
        return False

    # Basic email pattern check
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, message):
        return False

    # Use Pydantic for final validation (catches edge cases)
    try:
        from pydantic import validate_email
        validate_email(message)
        return True
    except Exception:  # Catch ALL exceptions - Pydantic v2 raises different types
        return False

###########Function changed into ASYNC Function for API wait/sync###########
async def run_orchestration(request: OrchestrationRequest) -> Tuple[AgentResponse, NLUAgentResponse, OrchestrationResponse]:
    """
    Main orchestration flow with intent-based routing.
    
    Flow:
    1. Load existing session context (if any)
    2. Master Agent - Classify intent
    3. NLU Agent - Extract entities
    4. Intent Router - Route to appropriate handler
    5. Data Agent - Retrieve account information
    6. Response Agent - Generate natural response
    7. Save session context for next turn
    """
    #context = build_initial_context(request) ####Removed to accomodate for session_store

    # Try to load existing session context
    existing_context = session_store.load(request.session_id, ConversationContext)

    if existing_context:
        # Update existing context with new message
        context = existing_context
        context.last_user_message = request.message
        logger.info(f"Resumed session: {request.session_id}")
    else:
        # Create fresh context
        context = build_initial_context(request)
        logger.info(f"New session: {request.session_id}")

    # Initialize agents
    master_agent = MasterAgent()
    nlu_agent = NLUAgent()
    intent_router = IntentRouter()
    response_agent = ResponseAgent()
    data_agent = DataAgent()

    # Check if user is providing an email address
    if context.last_user_message and is_email(context.last_user_message):
        context.email_address = context.last_user_message.strip()
        context.intent = "provide_email"
        context.agent_path.append("Email Detected")

        # Route to EmailAgent
        email_agent = EmailAgent()
        context = await email_agent.run_async(context)
    
    # Check if user is providing an ID number (13 digit SA ID)
    if context.last_user_message and is_id_number(context.last_user_message):
            # User provided ID number - store it and route to Data Agent
            id_number = context.last_user_message.strip().replace(" ", "").replace("-", "")
            context.id_number = id_number
            context.intent = "get_balance"  # Default intent when just ID is provided
            context.agent_path.append("ID Number Detected")
    
            # Call Data Agent directly
            context = await data_agent.run_async(context, id_number)
    else:
        #Normal Flow
        # Step 1: Master Agent - Classify intent
        context = master_agent.run(context)
    
        # Step 2: NLU Agent - Extract entities
        context = nlu_agent.run(context)
    
        # Check if user is providing requested input (e.g., ID number)
        if context.awaiting_input == "id_number":
            # User's message should be their ID number
            context.id_number = context.last_user_message.strip()
            context.awaiting_input = None
    
        # Step 3: Intent Router - Route based on intent and handle business logic
        context = intent_router.route(context)
    
        # Step 4: Data Agent - Fetch account info if needed
        if context.next_agent == "DataAgent" and context.id_number:
            context = await data_agent.run_async(context, context.id_number)
    
            ########Breaking http async Code########
        # if context.next_agent == "DataAgent" and context.id_number:
        #     context = await data_agent.run_async(context, context.id_number)
    
        # Step 5: Response Agent - Generate natural language response
        # Only run if we don't already have a good response from the handler
        if not context.final_response or context.next_agent == "ResponseAgent":
            context = response_agent.run(context)

    # Mark orchestration complete
    context.agent_path.append("Orchestrator")

    # Construct responses
    orchestration_response = OrchestrationResponse(
        session_id=context.session_id,
        debtor_id=context.debtor_id,
        response=context.final_response or "I'm sorry, I couldn't process your request.",
        agent_path=context.agent_path,
        status="completed" if context.understood_message else "failed",
        extras={
            "intent": context.intent,
            "next_agent": context.next_agent,
        },
    )

    agent_response = AgentResponse(
        last_user_message=context.last_user_message,
        summary=context.reasoning_result.summary if context.reasoning_result and context.reasoning_result.summary else "No summary available",
        reasoning_result=context.reasoning_result
    )

    nlu_agent_response = NLUAgentResponse(
        Entities=context.entities,
        reasoning_result=context.reasoning_result,
        nlu_reasoning=context.nlu_reasoning
    )

    # Save session context for next turn
    session_store.save(request.session_id, context)
    logger.debug(f"Saved session context: {request.session_id}")

    return agent_response, nlu_agent_response, orchestration_response
