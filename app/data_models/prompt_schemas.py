from typing import Literal, Optional

from pydantic import BaseModel, Field


Mode = Literal["translation", "definition", "learning", "general"]


class IntentResult(BaseModel):
    mode: Mode
    confidence: Literal["low", "medium", "high"]
    should_switch_mode: bool
    reason: str
    clarification_question: str = ""


class TranslationModeState(BaseModel):
    participant_a_language: str = "unknown"
    participant_b_language: str = "unknown"
    direction: Literal["auto", "a_to_b", "b_to_a"] = "auto"
    style: Literal["single_user", "two_person"] = "single_user"


class DefinitionModeState(BaseModel):
    current_term: Optional[str] = None
    language: str = "unknown"
    sense: Optional[str] = None


class LearningModeState(BaseModel):
    target_language: str = "unknown"
    native_language: str = "unknown"
    level: Literal["beginner", "intermediate", "advanced", "unknown"] = "unknown"
    current_topic: Optional[str] = None
    lesson_step: int = 0


class SessionState(BaseModel):
    active_mode: Mode = "general"
    previous_mode: Optional[Mode] = None

    translation: TranslationModeState = Field(default_factory=TranslationModeState)
    definition: DefinitionModeState = Field(default_factory=DefinitionModeState)
    learning: LearningModeState = Field(default_factory=LearningModeState)


class BaseModeResponse(BaseModel):
    response: str


class TranslationResponse(BaseModeResponse):
    mode: Literal["translation"] = "translation"
    source_language: str
    target_language: str
    translated_text: str
    

class DefinitionResponse(BaseModeResponse):
    mode: Literal["definition"] = "definition"
    term: str
    language: str = "unknown"
    part_of_speech: str = ""
    pronunciation: str = ""
    meaning: str
    examples: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    etymology: str = ""


class LearningResponse(BaseModeResponse):
    mode: Literal["learning"] = "learning"
    target_language: str = "unknown"
    native_language: str = "unknown"
    level: str = "unknown"
    topic: str = ""
    teaching_point: str = ""
    examples: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    new_vocabulary: list[dict] = Field(default_factory=list)
    exercises: list[str] = Field(default_factory=list)
    next_suggested_step: str = ""
