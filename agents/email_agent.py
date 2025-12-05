from __future__ import annotations

import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import os
from dotenv import load_dotenv

from schemas.context import ConversationContext

load_dotenv()


class EmailResult(BaseModel):
    """Result from email sending operation."""
    success: bool
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class EmailAgent:
    """
    Email Agent - Sends emails via IBIS API.
    
    Used for:
    - Sending approval requests for below-minimum payment plans
    - Sending confirmation emails
    - Other communication needs
    """

    def __init__(self):
        self.base_url = os.getenv("IBIS_BASE_URL", "")
        self.api_key = os.getenv("IBIS_API_KEY", "")
        self.user_id = os.getenv("IBIS_USER_ID", "")
        self.approval_email = os.getenv("IBIS_APPROVAL_EMAIL", "collections@company.com")

    async def send_approval_request(
            self,
            context: ConversationContext,
            to_email: str,
            matter_id: str,
            proposed_amount: float,
            minimum_payment: float,
            debtor_name: str,
            outstanding_balance: float
    ) -> EmailResult:
        """
        Send an approval request email for a below-minimum payment plan.
        """
        try:
            url = f"{self.base_url}/api/Communication/SendEmail"

            # Build email body
            today = datetime.now().strftime("%d %B %Y")
            email_body = f"""
Payment Plan Approval Request

Date: {today}

Debtor Details:
- Name: {debtor_name}
- Matter ID: {matter_id}
- Outstanding Balance: R{outstanding_balance:,.2f}

Payment Plan Request:
- Proposed Amount: R{proposed_amount:,.2f}
- Minimum Payment Required: R{minimum_payment:,.2f}
- Difference: R{minimum_payment - proposed_amount:,.2f} below minimum

The debtor has requested approval for a payment plan below the minimum 
required amount. Please review and respond to: {to_email}

---
This request was submitted via the AI Collections Assistant.
"""

            payload = {
                "EnvelopeHeader": {
                    "ApiKey": self.api_key
                },
                "EnvelopeBody": [
                    {
                        "ToEmailAddress": self.approval_email,  # Send to collections team
                        "EmailBody": email_body,
                        "EmailSubject": f"Payment Plan Approval Request - {matter_id}",
                        "MatterId": matter_id,
                        "UserId": int(self.user_id),
                        "HId": 0,
                        "IsOtp": False,
                        "HasAttachment": False
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
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            # Check for API errors
            footer = data.get("EnvelopeFooter", {})
            if footer.get("ExceptionThrown", False):
                return EmailResult(
                    success=False,
                    error_message=footer.get("ExceptionMessage", "Failed to send email"),
                    raw_response=data
                )

            return EmailResult(success=True, raw_response=data)

        except httpx.HTTPStatusError as e:
            return EmailResult(
                success=False,
                error_message=f"Email API request failed: {e.response.status_code}"
            )
        except Exception as e:
            return EmailResult(
                success=False,
                error_message=f"Failed to send email: {str(e)}"
            )

    async def run_async(self, context: ConversationContext) -> ConversationContext:
        """Process email sending based on context."""

        if "EmailAgent" not in context.agent_path:
            context.agent_path.append("EmailAgent")

        # Get required info from context
        if not context.email_address or not context.matter_details:
            context.final_response = "I'm missing some information needed to send the approval request."
            return context

        result = await self.send_approval_request(
            context=context,
            to_email=context.email_address,
            matter_id=context.matter_details.matter_id,
            proposed_amount=context.proposed_amount or 0,
            minimum_payment=context.matter_details.minimum_payment,
            debtor_name=context.matter_details.debtor_name,
            outstanding_balance=context.matter_details.outstanding_balance
        )

        if result.success:
            context.final_response = f"""✅ Approval Request Submitted

I've sent your payment plan approval request to our collections team.

Request Details:
• Proposed Amount: R{context.proposed_amount:,.2f}
• Your Email: {context.email_address}

You should receive a response within 24-48 business hours at your email address.

Is there anything else I can help you with?"""
            context.understood_message = True
        else:
            context.final_response = f"""I apologize, but I wasn't able to submit your approval request.

{result.error_message}

Please try again later or contact our support team directly."""

        return context