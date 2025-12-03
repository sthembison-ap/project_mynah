from __future__ import annotations

from typing import Dict, Any, Optional, List
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from schemas.context import ConversationContext, IntentType


# LLM Configuration - Same as other agents
model = ChatOllama(
    model="llama3.1:8b",
    base_url="http://192.168.100.203:11434",
    validate_model_on_init=True,
    temperature=0.7,  # Slightly higher for more natural responses
    timeout=300,
)


class ResponseOutput(BaseModel):
    """Structured output for the Response Agent."""
    response: str = Field(..., description="The natural language response to send to the user")
    follow_up_question: Optional[str] = Field(None, description="Optional follow-up question if more info needed")
    action_required: bool = Field(default=False, description="Whether an action is required from the system")


class ResponseAgent:
    """
    Response Agent - Generates natural, conversational responses.
    
    Responsibilities:
    - Generate human-friendly responses based on intent and context
    - Ask clarifying questions when entities are missing
    - Maintain a helpful, professional tone appropriate for debt resolution
    """

    # Required entities per intent for clarification flow
    REQUIRED_ENTITIES: Dict[str, List[str]] = {
        "setup_payment_plan": ["amount", "frequency"],
        "request_settlement_quote": ["amount"],
        "get_balance": [],
        "get_statement": [],
        "query_payment_history": [],
        "confirm_banking_details": [],
        "escalate_to_agent": [],
        "email_statement": [],
        "payment_date": [],
    }

    # Clarification questions for missing entities
    CLARIFICATION_QUESTIONS: Dict[str, str] = {
        "amount": "How much would you like to pay?",
        "frequency": "How often would you like to make payments? (e.g., weekly, monthly, or once-off)",
        "date": "When would you like to start or make this payment?",
        "payment_type": "Would you prefer to pay in installments or as a lump sum settlement?",
    }

    def __init__(self) -> None:
        self.llm = model
        self.structured_llm = self.llm.with_structured_output(ResponseOutput)
        self.prompt = self._build_prompt()
        self.chain = self.prompt | self.structured_llm

    @staticmethod
    def _build_prompt() -> ChatPromptTemplate:
        """Build the prompt template for generating responses."""

        system = """You are a friendly and professional debt resolution assistant.

Your job is to respond naturally to the debtor based on:
- Their detected intent
- Any entities (amounts, dates, frequencies) extracted from their message
- The current state of the conversation

TONE GUIDELINES:
- Be empathetic and understanding - debt is stressful
- Be clear and concise
- Use simple language, avoid jargon
- Be helpful and solution-oriented
- Never be condescending or judgmental

RESPONSE RULES:
1. If the intent is clear and all required info is available, confirm what you understood and explain next steps
2. If information is missing, politely ask for it
3. For balance inquiries, acknowledge and indicate you're retrieving the information
4. For payment plans, confirm the proposed amount and frequency
5. For small talk/greetings, be warm but guide toward how you can help
6. For unknown intents, politely ask for clarification

Always end with a clear next step or question if action is needed.
"""

        user = """Current conversation context:
- Session ID: {session_id}
- Intent detected: {intent}
- Entities extracted: {entities}
- Missing required info: {missing_entities}
- Previous reasoning: {reasoning}

Debtor's message: "{message}"

Generate a natural, helpful response. If information is missing, ask for it politely.
"""

        return ChatPromptTemplate.from_messages([
            ("system", system),
            ("user", user),
        ])

    def _get_missing_entities(self, context: ConversationContext) -> List[str]:
        """Check which required entities are missing for the current intent."""
        required = self.REQUIRED_ENTITIES.get(context.intent, [])

        if not context.entities:
            return required

        entities_dict = context.entities.model_dump()
        missing = [field for field in required if not entities_dict.get(field)]

        return missing

    def _build_prompt_values(self, context: ConversationContext) -> Dict[str, Any]:
        """Create values for the prompt template."""
        missing = self._get_missing_entities(context)

        entities_str = "None extracted"
        if context.entities:
            entities_dict = {k: v for k, v in context.entities.model_dump().items() if v is not None}
            if entities_dict:
                entities_str = ", ".join(f"{k}: {v}" for k, v in entities_dict.items())

        reasoning = context.nlu_reasoning or context.reasoning_result.summary if context.reasoning_result else "No reasoning available"

        return {
            "session_id": context.session_id,
            "intent": context.intent,
            "entities": entities_str,
            "missing_entities": ", ".join(missing) if missing else "None - all required info available",
            "reasoning": reasoning,
            "message": context.last_user_message,
        }

    def _generate_fallback_response(self, context: ConversationContext) -> str:
        """Generate a template-based response if LLM fails."""
        intent = context.intent
        missing = self._get_missing_entities(context)

        # If missing entities, ask for them
        if missing:
            question = self.CLARIFICATION_QUESTIONS.get(missing[0], f"Could you please provide your {missing[0]}?")
            return f"I'd be happy to help you with that. {question}"

        # Template responses by intent
        TEMPLATES = {
            "get_balance": "I'll look up your current balance for you. One moment please...",
            "get_statement": "I'll retrieve your statement. Please give me a moment...",
            "setup_payment_plan": f"I can help you set up a payment plan of {context.entities.amount if context.entities else 'the amount you mentioned'} {context.entities.frequency if context.entities and context.entities.frequency else 'as discussed'}. Shall I proceed with this arrangement?",
            "request_settlement_quote": "I'll calculate a settlement quote for you based on your account. One moment...",
            "query_payment_history": "Let me pull up your recent payment history...",
            "confirm_banking_details": "I'll confirm our banking details for you to make a secure payment.",
            "email_statement": "I'll arrange for your statement to be emailed to you.",
            "payment_date": "Let me check when your next payment is due...",
            "escalate_to_agent": "I understand you'd like to speak with a human agent. Let me connect you with someone who can help.",
            "unknown": "I'm not sure I understood your request. Could you please tell me if you'd like to:\n• Check your balance\n• Set up a payment plan\n• Get a settlement quote\n• Something else?",
        }

        return TEMPLATES.get(intent, TEMPLATES["unknown"])

    def run(self, context: ConversationContext) -> ConversationContext:
        """
        Generate a natural response and update the context.
        """
        try:
            prompt_values = self._build_prompt_values(context)
            result: ResponseOutput = self.chain.invoke(prompt_values)

            # Use the LLM-generated response
            response = result.response
            if result.follow_up_question:
                response = f"{response}\n\n{result.follow_up_question}"

        except Exception as e:
            # Fallback to template-based response
            print(f"ResponseAgent LLM error: {e}")
            response = self._generate_fallback_response(context)

        # Update context
        context.final_response = response

        if "ResponseAgent" not in context.agent_path:
            context.agent_path.append("ResponseAgent")

        return context
