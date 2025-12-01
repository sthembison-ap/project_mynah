from __future__ import annotations

from typing import Tuple

from schemas.context import ConversationContext, OrchestrationRequest, OrchestrationResponse, AgentResponse

from agents.master import MasterAgent

from agents.nlu import NLUAgent

def build_initial_context(request: OrchestrationRequest) -> ConversationContext:
    return ConversationContext(
        session_id=request.session_id, 
        debtor_id=request.debtor_id,
        last_user_message=request.message
    )

def run_orchestration(request: OrchestrationRequest) -> Tuple[ConversationContext, OrchestrationResponse]:
    context = build_initial_context(request)
    
    #1) Master Agent - classify intent, extract entities, take action
    agent = MasterAgent()
    nlu_agent = NLUAgent()

    # Capture the result from Agent run
    agent_result = agent.run(context)
    
    #2)NLU: refine intent & extract entities
    nlu_agent_result = nlu_agent.run(context)


    # Construct the OrchestrationResponse
    response_text = (
        f"Detected intent: {context.intent}. "
        f"(This is just the Master Agent stub; downstream agents still to be implemented.)"
    )
    context.final_response = response_text
    context.agent_path.append("Orchestrator")

    orchestration_response = OrchestrationResponse(
        session_id=context.session_id,
        debtor_id=context.debtor_id,
        response=response_text,
        agent_path=context.agent_path,
        status="completed" if context.understood_message else "failed",
        extra={},
    )

    agent_response = AgentResponse(
        last_user_message=context.last_user_message,
        summary=context.reasoning if hasattr(context, 'summary') else "No summary available",
        reasoning_result=context.reasoning_result
    )
    
    
    return agent_response, orchestration_response

    # Outstanding: NLU Agent -> Data Agent -> Reasoning Agent -> Response Agent
    # For now we just echo what we learned from Master Agent.

    # response_text = (
    #     f"Detected intent: {context.intent}. "
    #     f"(This is just the Master Agent stub; downstream agents still to be implemented.)"
    # )
    # context.final_response = response_text
    # context.agent_path.append("Orchestrator")
    # 
    # return OrchestratorResponse(
    #     session_id=context.session_id,
    #     debtor_id=context.debtor_id,
    #     response=response_text,
    #     agent_path=context.agent_path,
    #     status="completed",
    #     extra={},
    # )