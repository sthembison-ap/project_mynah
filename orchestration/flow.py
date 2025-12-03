from __future__ import annotations

from typing import Tuple

from schemas.context import ConversationContext, OrchestrationRequest, OrchestrationResponse, AgentResponse, NLUAgentResponse

from agents.master import MasterAgent

from agents.nlu import NLUAgent

import json #Importing this here just for TESTING Context dump
# New imports for intent routing and response generation
from routes.intent_router import IntentRouter
from agents.response_agent import ResponseAgent

def build_initial_context(request: OrchestrationRequest) -> ConversationContext:
    return ConversationContext(
        session_id=request.session_id, 
        debtor_id=request.debtor_id,
        last_user_message=request.message,
    )

def run_orchestration(request: OrchestrationRequest) -> Tuple[AgentResponse, NLUAgentResponse, OrchestrationResponse]:
    """
    Main orchestration flow with intent-based routing.
    
    Flow:
    1. Master Agent - Classify intent
    2. NLU Agent - Extract entities
    3. Intent Router - Route to appropriate handler
    4. Response Agent - Generate natural response
    """
    context = build_initial_context(request)

    # Initialize agents
    master_agent = MasterAgent()
    nlu_agent = NLUAgent()
    intent_router = IntentRouter()
    response_agent = ResponseAgent()

    # Step 1: Master Agent - Classify intent
    context = master_agent.run(context)

    # Step 2: NLU Agent - Extract entities
    context = nlu_agent.run(context)

    # Step 3: Intent Router - Route based on intent and handle business logic
    context = intent_router.route(context)

    # Step 4: Response Agent - Generate natural language response
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

    return agent_response, nlu_agent_response, orchestration_response
