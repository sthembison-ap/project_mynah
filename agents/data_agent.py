from __future__ import annotations

import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

from schemas.context import ConversationContext, MatterDetails

# Load environment variables
load_dotenv()


class IBISConfig:
    """IBIS API Configuration from environment variables."""
    BASE_URL = os.getenv("IBIS_BASE_URL", "")
    API_KEY = os.getenv("IBIS_API_KEY", "")
    USER_ID = os.getenv("IBIS_USER_ID", "")


#########Moving Class to context.py where it belongs########

# class MatterDetails(BaseModel):
#     """Parsed matter details from IBIS API response."""
#     idx: int
#     matter_id: str
#     status: str
#     outstanding_balance: float
#     capital_amount: float
#     minimum_payment: float
#     last_payment_amount: float
#     last_payment_date: str
#     client_name: str  # Creditor name
#     debtor_name: str
#     active_plan: bool
#     payment_method: str


class DataAgentResult(BaseModel):
    """Result from Data Agent operations."""
    success: bool
    matter_details: Optional[MatterDetails] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class DataAgent:
    """
    Data Agent - Fetches account information from IBIS API.
    
    Responsibilities:
    - Call IBIS API to get linked matter details
    - Parse and validate API responses
    - Handle API errors gracefully
    - Provide account information for payment arrangement validation
    """

    def __init__(self):
        self.config = IBISConfig()
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that all required configuration is present."""
        if not all([self.config.BASE_URL, self.config.API_KEY, self.config.USER_ID]):
            raise ValueError(
                "Missing IBIS configuration. Ensure IBIS_BASE_URL, IBIS_API_KEY, "
                "and IBIS_USER_ID are set in .env file."
            )
    ####Old Get Headers####
    # def _get_headers(self) -> Dict[str, str]:
    #     """Build API request headers."""
    #     return {
    #         "Content-Type": "application/json",
    #         "Authorization": f"Bearer {self.config.API_KEY}",
    #         "X-User-ID": self.config.USER_ID,
    #     }

    def _get_headers(self) -> Dict[str, str]:
        """Build API request headers."""
        return {
            "Content-Type": "application/json",
        }

    async def get_linked_matter_details(self, id_number: str) -> DataAgentResult:
        """
        Fetch linked matter details from IBIS API.
        
        Args:
            id_number: The user's ID number to look up
            
        Returns:
            DataAgentResult with matter details or error information
        """
        try:
            url = f"{self.config.BASE_URL}/api/Matter/GetLinkedMatterDetails"
            
            ######Old Payload Configuration######
            # payload = {
            #     "IdNumber": id_number
            # }
            payload = {
                "EnvelopeHeader": {
                    "ApiKey": self.config.API_KEY
                },
                "EnvelopeBody": [
                    {
                        "IdentityNumber": id_number,
                        "UserId": int(self.config.USER_ID)
                    }
                ],
                "EnvelopeFooter": {
                    "ExceptionThrown": False,
                    "ExceptionMessage": "",
                    "ResponseMessage": ""
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=payload
                )

                response.raise_for_status()
                data = response.json()

            # Check for API-level errors
            footer = data.get("EnvelopeFooter", {})
            if footer.get("ExceptionThrown", False):
                error_msg = footer.get("ExceptionMessage", "Unknown API error")
                # Handle common IBIS errors with user-friendly messages
                if "Index was out of range" in error_msg:
                    return DataAgentResult(
                        success=False,
                        error_message="No account found for the provided ID number. Please check your ID and try again.",
                        raw_response=data
                        
                    )
                return DataAgentResult(
                    success=False,
                    error_message=error_msg,
                    raw_response=data
                )

            # Parse the response
            body = data.get("EnvelopeBody", [])
            if not body:
                return DataAgentResult(
                    success=False,
                    error_message="No account found for the provided ID number.",
                    raw_response=data
                )

            # Take the first matter (or could present options if multiple)
            matter = body[0]

            matter_details = MatterDetails(
                idx=matter.get("Idx", 0),
                matter_id=matter.get("MatterID", ""),
                status=matter.get("Status", ""),
                outstanding_balance=matter.get("OutstandingBalance", 0.0),
                capital_amount=matter.get("CapitalAmount", 0.0),
                minimum_payment=matter.get("MinimumPayment", 0.0),
                last_payment_amount=matter.get("LastPaymentAmount", 0.0),
                last_payment_date=matter.get("LastPaymentDate", ""),
                client_name=matter.get("ClientName", "").strip(),
                debtor_name=matter.get("DebtorName", "").strip(),
                active_plan=matter.get("ActivePlan", False),
                payment_method=matter.get("PaymentMethod", ""),
            )

            return DataAgentResult(
                success=True,
                matter_details=matter_details,
                raw_response=data
            )

        except httpx.HTTPStatusError as e:
            return DataAgentResult(
                success=False,
                error_message=f"API request failed: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return DataAgentResult(
                success=False,
                error_message=f"Network error: {str(e)}"
            )
        except Exception as e:
            return DataAgentResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )

    def run(self, context: ConversationContext, id_number: str) -> ConversationContext:
        """
        Synchronous wrapper for the data agent.
        Use run_async for async contexts.
        """
        import asyncio
        result = asyncio.run(self.get_linked_matter_details(id_number))
        return self._update_context(context, result)

    async def run_async(self, context: ConversationContext, id_number: str) -> ConversationContext:
        """
        Async version of run for use in async contexts.
        """
        result = await self.get_linked_matter_details(id_number)
        return self._update_context(context, result)

    def _update_context(self, context: ConversationContext, result: DataAgentResult) -> ConversationContext:
        """Update conversation context with data agent results."""

        if "DataAgent" not in context.agent_path:
            context.agent_path.append("DataAgent")

        if result.success and result.matter_details:
            # Store matter details in context (you may need to extend ConversationContext)
            # For now, we'll build a response
            details = result.matter_details

            context.final_response = self._build_account_response(details, context)
            context.understood_message = True
        else:
            context.final_response = (
                f"I wasn't able to retrieve your account information. "
                f"{result.error_message or 'Please try again later.'}"
            )

        return context

    def _build_account_response(self, details: MatterDetails, context: ConversationContext) -> str:
        """Build a natural language response based on intent and account information."""

        # Format last payment date
        last_payment_display = "N/A"
        if details.last_payment_date and "1900-01-01" not in details.last_payment_date:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(details.last_payment_date.replace("Z", ""))
                last_payment_display = dt.strftime("%d %B %Y")
            except:
                last_payment_display = details.last_payment_date.split("T")[0]

        # Get first name for personalization
        first_name = details.debtor_name.split()[0] if details.debtor_name else "there"
        
        # Build response based on intent
        if context.intent == "get_balance" or context.intent == "ask_balance":
            response = f"""Thank you for verifying your account. Here are your balance details:

Account Balance:
• Matter Number: {details.matter_id}
• Creditor: {details.client_name}
• Outstanding Balance: R{details.outstanding_balance:,.2f}
• Original Amount: R{details.capital_amount:,.2f}
• Last Payment Date: {last_payment_display}

Would you like to set up a payment plan or get a settlement quote?"""

        elif context.intent == "setup_payment_plan" or context.intent == "create_payment_arrangement":
            # Get proposed payment from entities
            proposed_amount = "the amount you mentioned"
            proposed_frequency = "as discussed"
            if context.entities:
                if context.entities.amount:
                    proposed_amount = f"R{context.entities.amount:,.2f}"
                if context.entities.frequency:
                    proposed_frequency = context.entities.frequency

            response = f"""Thank you for providing your details. I've located your account.

Account Summary:
• Matter Number: {details.matter_id}
• Creditor: {details.client_name}
• Outstanding Balance: R{details.outstanding_balance:,.2f}
• Original Amount: R{details.capital_amount:,.2f}
• Minimum Payment Required: R{details.minimum_payment:,.2f}
• Last Payment Date: {last_payment_display}

Based on your request, I can set up a payment plan of {proposed_amount} {proposed_frequency}.

Would you like me to proceed with this arrangement?"""

        else:
            # Default response for other intents
            response = f"""I've located your account.

Account Details:
• Matter Number: {details.matter_id}
• Creditor: {details.client_name}
• Outstanding Balance: R{details.outstanding_balance:,.2f}
• Original Amount: R{details.capital_amount:,.2f}
• Last Payment Date: {last_payment_display}

How would you like to proceed?"""

        # Add POPIA notice footer
        response += """

POPIA Compliance Notice: Your personal information is processed in accordance with the Protection of Personal Information Act (POPIA). We only use your data to service your account and will not share it with third parties without your consent. You have the right to access, correct, or request deletion of your personal information."""
        ####GetFinancialStatement
        return response