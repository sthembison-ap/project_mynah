from __future__ import annotations

from langchain_ollama import ChatOllama, OllamaEmbeddings, OllamaLLM
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
#from uritemplate import partial

from schemas.context import ConversationContext, IntentType
from schemas.master_intent import MasterIntentOutput
#from . import OllamaLLM
import json #Importing this here just for TESTING Context dump

model = ChatOllama(
    model="llama3.1:8b",
    base_url="http://192.168.100.203:11434",  # Specify the server URL
    validate_model_on_init=True,
    temperature=0.4,
    timeout=300,  # Increase timeout to 60 seconds
)

MASTER_SYSTEM_PROMPT = """You are the Master Agent orchestrator.

Your job is to read the debtor's message and classify it into one of the following intents:

- get_balance
- get_statement
- request_settlement_quote
- setup_payment_plan
- query_payment_history
- query_guidelines
- escalate_to_agent
- unknown

Return ONLY a JSON object with fields:
- intent: one of the allowed labels
- reasoning: short explanation

Do NOT invent new labels.
"""

def build_master_chain():
    parser = PydanticOutputParser(pydantic_object=MasterIntentOutput)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MASTER_SYSTEM_PROMPT + "\\n\\nOutput format:\\n{format_instructions}"),
            ("human", "Debtor message: {message}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    llm = model
    chain = prompt | llm | parser
    return chain

class MasterAgent:
    def __init__(self):
        self.chain = build_master_chain()
        
    def run(self, context: ConversationContext) -> ConversationContext:
        result: MasterIntentOutput = self.chain.invoke({"message": context.last_user_message})
        #return self.chain.run(context) --PLACEHOLDER
        
        #update context:
        context.intent = result.intent
        context.agent_path.append("Master Agent")
        context.next_agent = "NLU Agent"
        if context.intent != "unknown":
            context.understood_message = True
            #if context.intent == IntentType.BALANCE else "Data Agent" --PLACEHOLDER
        # fixed route for now; NLU always follows
        # we can optionally store reasoning somewhere if useful
        
        #COMMENTED - BREAKING REASONING
        # if context.reasoning is None:
        #     from schemas.context import ReasoningResult
        #     context.reasoning = ReasoningResult(summary=result.reasoning)
        # else:
        #     context.reasoning.summary += result.reasoning

        if not hasattr(context, 'reasoning') or context.reasoning_result is None:
            from schemas.context import ReasoningResult
            context.reasoning_result = ReasoningResult(summary=result.reasoning)
        else:
            context.reasoning.summary += result.reasoning #TODO Might break the logic here if not handled at a later stage
        
            #context.last_user_message = result.response --PLACEHOLDER
        #return context
        # print("Testing Master Agent Context Dump:")
        # print(json.dumps(context.model_dump(), indent=2))
        # 
        # print("Dumping the entire Master JSON:")
        # print(context.entities.model_dump().values())
        
        return context