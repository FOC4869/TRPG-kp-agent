"""Small model outputs; game rules and numerical effects are never model fields."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionIntent = Literal[
    "look", "investigate", "careful_search", "talk", "rule_question", "leave", "clarify", "unsupported"
]
TargetId = Literal["desk", "bookshelf", "fireplace", "butler", "room", "exit"]


class ActionPlan(BaseModel):
    """An intention for the scene validator, not permission to change the game."""

    model_config = ConfigDict(extra="forbid")

    intent: ActionIntent
    target_id: TargetId | None = None
    query: str | None = Field(default=None, max_length=500)
    question: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_intent_fields(self) -> "ActionPlan":
        if self.intent == "rule_question" and not (self.query and self.query.strip()):
            raise ValueError("rule_question requires a nonempty query")
        if self.intent == "clarify" and not (self.question and self.question.strip()):
            raise ValueError("clarify requires a nonempty question")
        return self


class Narration(BaseModel):
    """Public wording plus evidence IDs; these IDs are checked against retrieval."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list)
