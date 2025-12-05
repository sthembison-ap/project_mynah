from __future__ import annotations

from langchain_ollama import ChatOllama, OllamaEmbeddings, OllamaLLM
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate

from typing import Any, Dict

from pydantic import BaseModel

from schemas.context import ConversationContext, NLUEntities, NLUResult, IntentType

import json #Importing this here just for TESTING Context dump


model = ChatOllama(
    model="llama3.1:8b",
    base_url="http://192.168.100.203:11434",  # Specify the server URL
    validate_model_on_init=True,
    temperature=0.7,
    timeout=300,  # Increase timeout to 60 seconds
)


class NLUAgent:
    """
    Natural Language Understanding (NLU) agent.
    Responsibilities:
    - Extract entities (amount, currency, frequency, etc.) from the debtor's message.
    - DO NOT decide or override intent. Intent is set by MasterAgent.
    - Provide short reasoning to help with debugging and audits.
    """
    
    def __init__(self) -> None:
        #self.structured_llm = None #Structured LLM Output
        self.llm = model
        #Structured output: NLUResult (entities + reasoning, no intent)
        structured_llm = self.llm.with_structured_output(NLUResult)
        
        self.prompt = self._build_prompt()
        
        # Mirror MasterAgent: prompt -> LLM(with_structured_output)
        self.chain = self.prompt | structured_llm
        #self.output_parser = PydanticOutputParser(pydantic_object=NLUEntities) --Deprecating this, agent is redesigned
        
        
    
    @staticmethod
    def _build_prompt() -> ChatPromptTemplate:
        """
        Prompt template for extracting intent and entities from LLM output.
        """

        system  = (
            """You are an NLU (Natural Language Understanding) component in a debt resolution contact centre.
            
            Your ONLY job is to extract entities from the debtor's message. You do NOT classify intent.
            The intent has already been determined by the Master Agent and is provided for context.
            
            Output a STRICT JSON structure with:
            - entities: key financial and scheduling details extracted from the message
            - reasoning: short explanation of what you extracted and why
            
            Entity fields to extract:
            - amount: monetary amount mentioned (as a number, e.g., 500.00)
            - currency: currency code (default to 'ZAR' for South African Rand)
            - frequency: payment frequency ('weekly', 'monthly', 'once_off', etc.)
            - payment_type: type of payment ('installment', 'settlement', 'lump_sum')
            - date: any date mentioned (ISO format if possible)
            
            IMPORTANT RULES:
            - If no amount is clearly mentioned, leave amount as null.
            - If the currency is unclear but looks like South African Rand, use 'ZAR'.
            - If the debtor mentions a number of months, infer the frequency as 'monthly'.
            - If they mention 'once-off', 'one payment', 'lump sum', set frequency = 'once_off'.
            - If you are unsure about anything, leave that field as null.
            - DO NOT infer or output any intent - that is not your responsibility.
           """
        )
        
        user = (
            "Context:\n"
            "- session_id: {session_id}\n"
            "- debtor_id: {debtor_id}\n"
            "- intent (already classified by MasterAgent): {intent}\n\n"
            "Debtor's latest message:\n"
            "\"\"\"{debtor_message}\"\"\"\n\n"
            "Extract all relevant entities from this message and explain your reasoning."
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
                #"current_intent": context.intent, -- Causes ChatPromptTemplate to fail
                "intent": context.intent,  # Corrected key name - To stop ChatPromptTemplate from failing
                "debtor_message": context.last_user_message,
            }
    
            return {
                "conversation_context": conversation_snapshot,
                "session_id": context.session_id,
                "debtor_id": context.debtor_id,
                "intent": context.intent,
                "debtor_message": context.last_user_message,
            }

    def run(self, context: ConversationContext) -> ConversationContext:
        """
        Execute the NLU step and update the context.
        """
        if not context.last_user_message:
            # Nothing to do
            return context
    
        prompt_values = self._build_prompt_values(context)
        nlu_result: NLUResult = self.chain.invoke(prompt_values)
    
        # Call the LLM with structured output
        #nlu_result: NLUResult = self.structured_llm.invoke(prompt) --Deprecating this line due to 

        # Update context with extracted entities + reasoning
        #context.intent = nlu_result.intent --REMOVING (NLU Agent should not generate its own Intent
        context.entities = nlu_result.entities
        context.nlu_reasoning = nlu_result.reasoning
        if context.entities and any(context.entities.model_dump().values()): #--Why dumping the entire JSON - Reason is checking all the returned Entities
            context.understood_message = True
        
    
        # Mark path
        if "NLUAgent" not in context.agent_path:
            context.agent_path.append("NLUAgent")

        return context