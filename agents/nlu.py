from __future__ import annotations

from langchain_ollama import ChatOllama, OllamaEmbeddings, OllamaLLM
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate

from typing import Any, Dict

from pydantic import BaseModel

from schemas.context import ConversationContext, NLUEntities, IntentType


model = ChatOllama(
    model="llama3.1:8b",
    base_url="http://192.168.100.203:11434",  # Specify the server URL
    validate_model_on_init=True,
    temperature=0.4,
    timeout=300,  # Increase timeout to 60 seconds
)


class NLUAgent:
    """
    Natural Language Understanding (NLU) agent.

    Responsibilities:
    - Interpret the debtor's latest message.
    - Classify intent (arrangement, settlement, balance query, etc.).
    - Extract structured entities (amount, currency, frequency, etc.).
    - Provide short reasoning for debugging and audits.
    """
    
    def __init__(self) -> None:
        self.llm = model
        
        #Use structured output parser to extract entities from LLM output
        self.output_parser = PydanticOutputParser(pydantic_object=NLUEntities)
        self.prompt = self.build_prompt()
        
    
    @staticmethod
    def build_prompt() -> ChatPromptTemplate:
        """
        Prompt template for extracting intent and entities from LLM output.
        """

        system  = (
        """You are an NLU component in a debt resolution contact centre.
        
        Your job is to interpret a debtor's message and output a STRICT JSON
        structure with:
        - intent: what the debtor is trying to do
        - entities: key financial and scheduling details
        - reasoning: short explanation
        
        Possible intents:
        - create_payment_arrangement: debtor wants to pay in instalments.
        - request_settlement: debtor wants to settle the debt with a lump sum or reduced amount.
        - ask_balance: debtor is asking about current balance or how it was calculated.
        - small_talk: 'hi', 'thank you', etc., with no real financial action required.
        - other: anything that does not match the above.
        IMPORTANT RULES:
        - If no amount is clearly mentioned, leave amount as null.
        - If the currency is unclear but looks like South African Rand, use 'ZAR'.
        - If the debtor mentions a number of months, map it to number_of_payments.
        - If they mention 'once-off', 'one payment', or similar, set lump_sum = true and frequency = 'once'.
       - If you are unsure about anything, leave that field as null or 'unknown'
       """
        )
        
        user = (
            """Conversation context (may be partial): {conversation_context}
            Debtor's latest message: {debtor_message}
        "Now carefully decide the intent, extract entities, and explain your reasoning.
        """
        )

        return ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("user", user),
            ]
        )

def _build_prompt_values(self, context: ConversationContext) -> Dict[str, Any]:
        """
        Create values passed into the prompt template.
        We keep context light to avoid leaking too much info.
        """
    # You can enrich this with more context later (previous turns, crm data etc.)
        conversation_snapshot = {
            "session_id": context.session_id,
            "debtor_id": context.debtor_id,
            "current_intent": context.intent,
        }

        return {
            "conversation_context": conversation_snapshot,
            "debtor_message": context.last_user_message,
        }

# def run(self, context: ConversationContext) -> ConversationContext:
#     """
#     Execute the NLU step and update the context.
#     """
#     if not context.last_user_message:
#         # Nothing to do
#         return context
# 
#     prompt_values = self._build_prompt_values(context)
#     prompt = self.prompt.format(**prompt_values)
# 
#     # Call the LLM with structured output
#     nlu_result: NLUResult = self.structured_llm.invoke(prompt)
# 
#     # Update context
#     context.intent = nlu_result.intent
#     context.entities = nlu_result.entities
#     context.nlu_reasoning = nlu_result.reasoning
# 
#     # Mark path
#     if "NLUAgent" not in context.agent_path:
#         context.agent_path.append("NLUAgent")
# 
#     return context