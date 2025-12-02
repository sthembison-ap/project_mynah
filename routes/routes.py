from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas.context import InteractionRequest, InteractionResponse, AccountSnapshot
from orchestration.flow import OrchestrationRequest, run_orchestration

import json #Importing this here just for TESTING Context dump

router = APIRouter(tags=["interaction"])


@router.post("/interact", response_model=InteractionResponse)
async def interact(req: InteractionRequest) -> InteractionResponse:
    """
    Main interaction endpoint for external channels.

    - Accepts a debtor message + IDs
    - Runs the LangChain/LangGraph orchestration
    - Returns a structured response
    """
    # Map API request to orchestration DTO
    orch_req = OrchestrationRequest(
        session_id=req.session_id,
        debtor_id=req.debtor_id,
        message=req.message,
        channel=req.channel,
    )

    context = run_orchestration(orch_req)

    # Decide what message to return.
    # Once ResponseAgent is implemented, I'll have context.final_response.
    # For now a placeholder.
    if hasattr(context, "final_response") and getattr(context, "final_response") is not None:
        outgoing_message = context.final_response  # type: ignore[attr-defined]
    else:
        # Intermediate placeholder until ResponseAgent is done
        outgoing_message = (
            "Your request has been processed. "
            "Intent: {intent}. "
            "This environment is still in developer mode; "
            "a full natural-language response will be added soon."
        )#.format(intent=context.intent or "unknown")

    # Map account data to the public snapshot, if available
    account_snapshot = None
    # if context.account_data is not None:
    #     account_snapshot = AccountSnapshot(
    #         account_number=context.account_data.account_number,
    #         full_name=context.account_data.full_name,
    #         current_balance=context.account_data.current_balance,
    #         status=context.account_data.status,
    #         product_type=context.account_data.product_type,
    #     )

    print("Testing API Endpoint Context Dump:")
    print(json.dumps(orch_req.model_dump(), indent=2))

    # print("Dumping the entire Master JSON:")
    # print(context.entities.model_dump().values())
    
    # Build the API response
    api_response = InteractionResponse(
        session_id=orch_req.session_id,
        debtor_id=orch_req.debtor_id or req.debtor_id,
        #intent=orch_req.intent,
        message=outgoing_message,
        #entities=orch_req.entities,
        #agent_path=orch_req.agent_path,
        #errors=getattr(orch_req, "errors", []),
        account=account_snapshot,
        #book_rules=orch_req.book_rules,
        #recent_payments=orch_req.payment_history,
        # debug_context={
        #     "nlu_reasoning": getattr(context, "nlu_reasoning", None),
        #     "master_reasoning": getattr(context, "master_reasoning", None),
        # },
    )
    return api_response