from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SessionCreatePayload(BaseModel):
    scope: Literal["federal", "state", "both"] = "both"
    state_code: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    depth_mode: Literal["quick", "standard", "deep"] = "standard"


class AnswerPayload(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class QuestionOptionOut(BaseModel):
    label: str
    value: Any


class QuestionOut(BaseModel):
    key: str
    prompt: str
    hint: Optional[str] = None
    input_type: str
    sensitivity_level: str
    options: Optional[list[QuestionOptionOut]] = None


class SessionEnvelope(BaseModel):
    session_id: str
    next_question: Optional[QuestionOut]
    provisional_result_count: int = 0


class CompareScenarioInput(BaseModel):
    name: str
    description: Optional[str] = None
    answers: dict[str, Any] = Field(default_factory=dict)


class ComparePayload(BaseModel):
    scenarios: list[CompareScenarioInput] = Field(default_factory=list)
