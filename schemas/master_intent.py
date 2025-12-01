from typing import Literal, Optional
from pydantic import BaseModel

from .context import IntentType


class MasterIntentOutput(BaseModel):
    intent: IntentType
    reasoning: Optional[str] = None
