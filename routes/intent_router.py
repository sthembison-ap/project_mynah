from __future__ import annotations

from typing import Dict, Type, Optional, Callable
from abc import ABC, abstractmethod

from schemas.context import ConversationContext, IntentType


class IntentHandler(ABC):
    """Base class for intent handlers."""

    @abstractmethod
    def handle(self, context: ConversationContext) -> ConversationContext:
        """Process the intent and update context."""
        pass


class BalanceHandler(IntentHandler):
    """Handler for get_balance intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        # TODO: Integrate with Data Agent to fetch actual balance
        # For now, mark that we need to fetch balance data
        context.next_agent = "DataAgent"

        # Placeholder - in production, this would call your CRM/Excalibur API
        if context.crm:
            balance_info = f"Your current balance is {context.crm.currency} {context.crm.balance:.2f}"
        else:
            balance_info = "I'm retrieving your balance information..."

        context.final_response = balance_info
        return context


class PaymentPlanHandler(IntentHandler):
    """Handler for setup_payment_plan intent."""

    REQUIRED_ENTITIES = ["amount", "frequency"]

    def handle(self, context: ConversationContext) -> ConversationContext:
        entities = context.entities.model_dump() if context.entities else {}

        # Check for missing required entities
        missing = [e for e in self.REQUIRED_ENTITIES if not entities.get(e)]

        if missing:
            # Need more information - ResponseAgent will ask
            context.next_agent = "ResponseAgent"
            return context

        # All info available - proceed with arrangement logic
        amount = entities.get("amount")
        frequency = entities.get("frequency")

        # TODO: Integrate with Reasoning Agent to validate against book rules
        # For now, acknowledge the request
        context.final_response = (
            f"I can set up a payment plan of R{amount:.2f} {frequency}. "
            "Let me verify this against your account terms..."
        )
        context.next_agent = "ReasoningAgent"

        return context


class SettlementHandler(IntentHandler):
    """Handler for request_settlement_quote intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        entities = context.entities.model_dump() if context.entities else {}
        amount = entities.get("amount")

        if amount:
            context.final_response = (
                f"I'll calculate a settlement quote based on your proposed amount of R{amount:.2f}. "
                "Please give me a moment to review your account..."
            )
        else:
            context.final_response = (
                "I can help you with a settlement quote. "
                "Would you like me to calculate the best settlement amount for your account?"
            )

        context.next_agent = "ReasoningAgent"
        return context


class StatementHandler(IntentHandler):
    """Handler for get_statement intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        context.final_response = (
            "I'll retrieve your statement. "
            "Would you like to view it here or have it emailed to you?"
        )
        context.next_agent = "DataAgent"
        return context


class PaymentHistoryHandler(IntentHandler):
    """Handler for query_payment_history intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        # TODO: Fetch from Data Agent
        context.final_response = "Let me pull up your recent payment history..."
        context.next_agent = "DataAgent"
        return context


class BankingDetailsHandler(IntentHandler):
    """Handler for confirm_banking_details intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        # Return standard banking details (these would come from config in production)
        context.final_response = (
            "Here are our verified banking details for payments:\n\n"
            "Bank: [Your Bank Name]\n"
            "Account Name: [Account Name]\n"
            "Account Number: [Account Number]\n"
            "Branch Code: [Branch Code]\n"
            "Reference: Please use your account number as reference.\n\n"
            "⚠️ Please verify these details match our official correspondence before making any payment."
        )
        return context


class EscalateHandler(IntentHandler):
    """Handler for escalate_to_agent intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        context.final_response = (
            "I understand you'd like to speak with a human agent. "
            "I'm connecting you now. Please hold while I transfer you to the next available consultant.\n\n"
            "Alternatively, you can call us directly at [Phone Number] during business hours."
        )
        context.next_agent = "HumanHandoff"
        return context


class PaymentDateHandler(IntentHandler):
    """Handler for payment_date intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        # TODO: Fetch from Data Agent
        context.final_response = "Let me check your next payment due date..."
        context.next_agent = "DataAgent"
        return context


class EmailStatementHandler(IntentHandler):
    """Handler for email_statement intent."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        context.final_response = (
            "I'll send your statement to the email address on file. "
            "You should receive it within the next few minutes. "
            "Would you like me to confirm the email address we have?"
        )
        return context


class SmallTalkHandler(IntentHandler):
    """Handler for greetings and small talk."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        context.final_response = (
            "Hello! I'm here to help you with your account. "
            "I can assist you with:\n"
            "• Checking your balance\n"
            "• Setting up a payment plan\n"
            "• Getting a settlement quote\n"
            "• Viewing your payment history\n"
            "• And more!\n\n"
            "How can I help you today?"
        )
        return context


class UnknownIntentHandler(IntentHandler):
    """Handler for unknown/unrecognized intents."""

    def handle(self, context: ConversationContext) -> ConversationContext:
        context.final_response = (
            "Hi! Could you please tell me if you'd like to:\n\n"
            "• Check your balance - See your current account balance\n"
            "• Make a payment - Set up a payment plan or once-off payment\n"
            "• Get a settlement quote - See options to settle your account\n"
            "• View payment history - See your recent payments\n"
            "• Speak to an agent - Connect with a human consultant\n\n"
            "Just let me know how I can help!"
        )
        return context


class IntentRouter:
    """
    Routes conversations to appropriate handlers based on intent.
    
    This provides clean separation of concerns - each intent has its own
    handler that knows how to process that specific type of request.
    """

    # Map intents to their handlers
    HANDLERS: Dict[str, Type[IntentHandler]] = {
        "get_balance": BalanceHandler,
        "get_statement": StatementHandler,
        "request_settlement_quote": SettlementHandler,
        "setup_payment_plan": PaymentPlanHandler,
        "query_payment_history": PaymentHistoryHandler,
        "query_guidelines": UnknownIntentHandler,  # TODO: Implement
        "escalate_to_agent": EscalateHandler,
        "email_statement": EmailStatementHandler,
        "payment_date": PaymentDateHandler,
        "confirm_banking_details": BankingDetailsHandler,
        "unknown": UnknownIntentHandler,
        # NLU intents (from NLUResult)
        "create_payment_arrangement": PaymentPlanHandler,
        "request_settlement": SettlementHandler,
        "ask_balance": BalanceHandler,
        "small_talk": SmallTalkHandler,
        "other": UnknownIntentHandler,
    }

    def __init__(self):
        self._handler_cache: Dict[str, IntentHandler] = {}

    def _get_handler(self, intent: str) -> IntentHandler:
        """Get or create handler instance for the given intent."""
        if intent not in self._handler_cache:
            handler_class = self.HANDLERS.get(intent, UnknownIntentHandler)
            self._handler_cache[intent] = handler_class()
        return self._handler_cache[intent]

    def route(self, context: ConversationContext) -> ConversationContext:
        """
        Route the conversation to the appropriate handler based on intent.
        
        Args:
            context: The current conversation context with intent set
            
        Returns:
            Updated conversation context after handler processing
        """
        intent = context.intent or "unknown"
        handler = self._get_handler(intent)

        # Add routing info to agent path
        if "IntentRouter" not in context.agent_path:
            context.agent_path.append("IntentRouter")

        # Execute the handler
        return handler.handle(context)

    def register_handler(self, intent: str, handler_class: Type[IntentHandler]) -> None:
        """
        Register a custom handler for an intent.
        
        This allows extending the router with new handlers without modifying this class.
        """
        self.HANDLERS[intent] = handler_class
        # Clear cache for this intent to use new handler
        if intent in self._handler_cache:
            del self._handler_cache[intent]
