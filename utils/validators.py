from pydantic import EmailStr, ValidationError
from typing import Tuple

from schemas.context import ConversationContext


def validate_email_address(email: str) -> Tuple[bool, str, str]:
    """
    Validate an email address using Pydantic.
    
    Returns:
        Tuple of (is_valid, normalized_email, error_message)
    """
    if not email or not email.strip():
        return False, "", "Please provide an email address."

    cleaned = email.strip().lower()

    try:
        from pydantic import validate_email
        validated = validate_email(cleaned)
        return True, validated[1], ""  # validated[1] is the normalized email
    except ValidationError as e:
        return False, "", "That doesn't look like a valid email address. Please check and try again."
