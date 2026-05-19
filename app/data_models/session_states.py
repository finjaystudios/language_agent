from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["translation", "definition", "learning", "general"]


class TranslationModeState(BaseModel):
    participant_a_language: str = "unknown"
    participant_b_language: str = "unknown"
    direction: Literal["auto", "a_to_b", "b_to_a"] = "auto"
    style: Literal["single_user", "two_person"] = "single_user"


class DefinitionModeState(BaseModel):
    current_term: None | str = None
    language: str = "unknown"
    sense: None | str = None


class LearningModeState(BaseModel):
    target_language: str = "unknown"
    native_language: str = "unknown"
    level: Literal["beginner", "intermediate", "advanced", "unknown"] = "unknown"
    current_topic: None | str = None
    lesson_step: int = 0


class SessionState(BaseModel):
    active_mode: Mode = "general"
    previous_mode: None | Mode = None

    translation: TranslationModeState = Field(default_factory=TranslationModeState)
    definition: DefinitionModeState = Field(default_factory=DefinitionModeState)
    learning: LearningModeState = Field(default_factory=LearningModeState)
