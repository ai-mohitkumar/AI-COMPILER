from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentSignal(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class UserIntent(BaseModel):
    prompt: str
    app_name: str
    app_type: str
    summary: str
    features: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    suggested_entities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    needs_auth: bool = True
    ambiguity: Literal["low", "medium", "high"] = "low"
    signals: list[IntentSignal] = Field(default_factory=list)
