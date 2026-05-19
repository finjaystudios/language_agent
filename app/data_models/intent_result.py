from typing import Literal

from pydantic import BaseModel

Mode = Literal["translation", "definition", "learning", "general"]


class IntentResult(BaseModel):
    mode: Mode
    confidence: Literal["low", "medium", "high"]
    should_switch_mode: bool
    reason: str
    clarification_question: str = ""
