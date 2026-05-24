from typing import Literal

from pydantic import BaseModel, Field


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
