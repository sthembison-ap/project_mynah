from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Lateral

#----------- NLU / Intent Layer -----------

############Intents from Customer Portal Workflow Diagram############

IntentType = Literal[
    "get_balance", #Check my account balance
    "get_statement",
    "request_settlement_quote",
    "setup_payment_plan", #Create an arrangement
    "query_payment_history",
    "query_guidelines",
    "escalate_to_agent", #"Chat to Agent"
    "email_statement", #Email Statement
    "payment_date", #When is my next payment due?
    "confirm_banking_details", #Confirm Banking Details
    "unknown",
]

class NLUEntities(BaseModel):
    amount: Optional[float] = Field(None, description="The amount of money requested")
    currency: Optional[str] = Field(None, description="The currency of the amount")
    frequency: Optional[str] = Field(None, description="The frequency of the payment") #e.g. "monthly", "once_off"
    payment_type: Optional[str] = Field(None, description="The type of payment") #e.g. "installment", "settlement"
    date: Optional[str] = Field(None, description="The date of the payment") #ISO date format (if extracted)
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw entities extracted from the user's message")


class NLUResult(BaseModel):
    """NLU output for entity extraction and reasoning only.
    
    Note: Intent classification is handled by MasterAgent.
    NLU Agent focuses solely on extracting entities from the message.
    """
    model_config = ConfigDict(extra="ignore")

    entities: NLUEntities
    reasoning: str = Field(
        description="Short explanation of why these entities were extracted."
    )

class IncomingMessage(BaseModel):
    message: str = Field(..., description="The user's message")
    debtor_id: str = Field(..., description="The debtor's ID")
    session_id: str = Field(..., description="The session ID for the conversation")
    #nlu_intent: IntentType = Field(..., description="The intent of the user's message") -- PLACEHOLDER
    
    
#----------- Excalibur / Data Layer -----------

class BookRulesModule(BaseModel):
    global_minimum_installment: float = Field(..., description="The minimum installment amount for the book rules module")
    max_term_months: int = Field(..., description="The maximum term (in months) for the book rules module")
    settlement_approval_threshold: float = Field(..., description="The settlement approval threshold for the book rules module") # e.g. 0.15 for 15%
    
class PaymentHistoryEntity(BaseModel):
    amount: float = Field(..., description="The amount of the payment")
    date: str = Field(..., description="The date of the payment")
    status: str = Field(..., description="The status of the payment") #e.g. "success", "failed"
    
class PaymentHistoryModule(BaseModel):
    has_broken_arrangements: bool = Field(..., description="Whether the debtor has broken arrangements")
    last_arrangement_status: Optional[str] = Field(None, description="The last arrangement status of the debtor")
    recent_payments: List[PaymentHistoryEntity] = Field(default_factory=list, description="The most recent payments of the debtor")
    
    
class ExcaliburAccount(BaseModel):
    balance: float = Field(..., description="The balance of the account")
    
    
class ExcaliburContext(BaseModel):
    account_id: str = Field(..., description="The Excalibur Matter Number of the account")
    balance: float = Field(..., description="The balance of the account")
    currency: str = Field(..., description="The currency of the account")
    status: str = Field(..., description="The status of the account")
    book_rules: BookRulesModule = Field(..., description="The book rules module of the account")
    payment_history: PaymentHistoryModule = Field(..., description="The payment history module of the account")
    
    
class ArrangementReasoning(BaseModel):
    meets_minimum_installment: bool = Field(..., description="Whether the arrangement meets the minimum installment requirement")
    proposed_installment_amount: Optional[float] = Field(None, description="The proposed installment amount (if applicable)")
    term_months: Optional[int] = Field(None, description="The term (in months) of the arrangement (if applicable)")
    requires_human_review: bool = Field(..., description="Whether the arrangement requires human review")
    reason: Optional[str] = Field(None, description="The reason for the arrangement (if applicable)")
    
    
class SettlementReasoning(BaseModel):
    proposed_settlement_amount: Optional[float] = Field(None, description="The proposed settlement amount (if applicable)")
    discount_ratio: Optional[float] = Field(None, description="The discount ratio of the settlement (if applicable)")
    above_approval_threshold: bool = Field(..., description="Whether the settlement is above the approval threshold")
    requires_manager_approval: bool = Field(..., description="Whether the settlement requires manager approval")
    reason: Optional[str] = Field(None, description="The reason for the settlement (if applicable)")
    
    
class ReasoningResult(BaseModel):
    arrangement: Optional[ArrangementReasoning] = Field(None, description="The arrangement reasoning result")
    settlement: Optional[SettlementReasoning] = Field(None, description="The settlement reasoning result")
    summary: Optional[str] = Field(None, description="A summary of the reasoning result")
    #Want to improve the reasoning result.
    
#----------- Overall Context -----------

class ConversationContext(BaseModel):
    session_id: str = Field(..., description="The session ID for the conversation")
    debtor_id: str = Field(..., description="The debtor's ID")
    last_user_message: Optional[str] = Field(None, description="The last user message sent in the conversation")
    
    # path & orchestration layer:
    intent: IntentType = "unknown"
    entities: NLUEntities = Field(default_factory=NLUEntities, description="The entities extracted from the user's message")
    agent_path: List[str] = Field(default_factory=list, description="The agent path taken by the conversation")
    next_agent: Optional[str] = Field(None, description="The next agent to be taken by the conversation")
    understood_message: bool = False
    
    # data layer:
    crm: Optional[ExcaliburContext] = Field(None, description="The Excalibur context of the conversation")
    
    # reasoning layer:
    reasoning_result: Optional[ReasoningResult] = Field(None, description="The reasoning result of the Master Agent conversation")
    nlu_reasoning: Optional[str] = Field(None, description="The reasoning result of the NLU layer")
    
    # final response:
    final_response: Optional[str] = Field(None, description="The final response to be sent to the user")
    
class OrchestrationRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    debtor_id: str = Field(..., description="The debtor's ID")
    session_id: str = Field(..., description="The session ID for the conversation")
    channel: Optional[str] = Field(None, description="The channel of the request") #Added for the API endpoint - Should be handled in main.py as well
    #locale: Optional[str] = Field(None, description="The locale of the request") #Added for the API endpoint - Should be handled in main.py as well --NOT IN USE FOR NOW
    
class OrchestrationResponse(BaseModel):
    session_id: str = Field(..., description="The session ID for the conversation")
    debtor_id: str = Field(..., description="The debtor's ID")
    response: str = Field(..., description="The response to be sent to the user")
    agent_path: List[str] = Field(default_factory=list, description="The agent path taken by the conversation")
    status: Literal["completed", "failed"] = Field(..., description="The status of the conversation")
    extras: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extra information about the conversation")

class AgentResponse(BaseModel):
    last_user_message: Optional[str] = Field(None, description="The last user message sent in the conversation")
    summary: str = Field(..., description="The summary response to be sent to the user")
    reasoning_result: Optional[ReasoningResult] = Field(None, description="The reasoning result of the conversation")
    
    
    
class NLUAgentResponse(BaseModel):
    Entities: NLUEntities
    reasoning_result: Optional[ReasoningResult] = Field(None, description="The reasoning result of the conversation")
    nlu_reasoning: Optional[str] = Field(None, description="The reasoning result of the NLU layer")

    model_config = {
        "arbitrary_types_allowed": True
    }
    
#----------- API Request Body Schema -----------
class InteractionRequest(BaseModel):
    """
    Request body for the /interact endpoint.
    This is what your channels / frontends will send.
    """
    session_id: str = Field(..., description="Unique session/conversation ID.")
    debtor_id: str = Field(..., description="External debtor/account identifier.")
    message: str = Field(..., description="The debtor's latest message text.")
    channel: Optional[str] = Field(
        default=None,
        description="Origin channel, e.g. 'whatsapp', 'webchat', 'voice_transcript'.",
    )
    # I want to pull `locale` from Excalibur Localization API
    locale: Optional[str] = Field(default="en-ZA", description="Locale, e.g. 'en-ZA'.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional arbitrary metadata from the Debtor Portal.",
    )

#Minimal Projection of Excalibur data structure
class AccountSnapshot(BaseModel):
    """
    Minimal, safer projection of CRMAccount for API consumers.
    Adjust as needed (or expose CRMAccount directly if you prefer).
    """
    account_number: str
    full_name: Optional[str] = None
    current_balance: float
    status: str
    product_type: Optional[str] = None

#Feels like a duplication of concerns but keeping for now
class InteractionResponse(BaseModel):
    """
    Response body for the /interact endpoint.
    """
    session_id: str = Field(..., description="The session ID for the conversation")
    debtor_id: str = Field(..., description="External debtor/account identifier.")
    intent: Optional[str] = None
    message: str = Field(
        ...,
        description="Final or intermediate message back to the debtor. "
                    "Once ResponseAgent is implemented this will be the real reply.",
    )

    # Structured info for your channels/UX / debugging
    entities: Optional[NLUEntities] = None
    agent_path: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # Optional data snapshots (make them as rich as you like)
    account: Optional[AccountSnapshot] = None
    book_rules: Optional[BookRulesModule] = None
    recent_payments: List[PaymentHistoryModule] = Field(default_factory=list)

    # Optional: attach raw context for debugging (turn off in prod!)
    debug_context: Optional[dict[str, Any]] = None

#----------- Master Agent Prompt Schema -----------
class Persona(BaseModel):
    role: str
    description: str

class Objective(BaseModel):
    goal: str
    priority_tasks: List[str]
    secondary_task: str

class Mandate(BaseModel):
    constraints: List[str]

class Layout(BaseModel):
    response_style: str
    format_note: str

class PomlFramework(BaseModel):
    persona: Persona
    objective: Objective
    mandate: Mandate
    layout: Layout

class MasterAgentPrompt(BaseModel):
    poml_framework: PomlFramework
