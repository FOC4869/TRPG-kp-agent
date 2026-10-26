"""Small model outputs; game rules and numerical effects are never model fields."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ActionIntent = Literal[
    "look", "investigate", "careful_search", "talk", "move", "use_item", "finish",
    "rule_question", "leave", "clarify", "unsupported"
]
TargetId = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class ActionPlan(BaseModel):
    """An intention for the scene validator, not permission to change the game."""

    model_config = ConfigDict(extra="forbid")

    intent: ActionIntent
    target_id: TargetId | None = None
    item_id: TargetId | None = None
    query: str | None = Field(default=None, max_length=500)
    question: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_intent_fields(self) -> "ActionPlan":
        if self.intent == "rule_question" and not (self.query and self.query.strip()):
            raise ValueError("rule_question requires a nonempty query")
        if self.intent == "clarify" and not (self.question and self.question.strip()):
            raise ValueError("clarify requires a nonempty question")
        if self.intent == "use_item" and (not self.item_id or not self.target_id):
            raise ValueError("use_item requires item_id and target_id")
        if self.item_id is not None and self.intent != "use_item":
            raise ValueError("item_id is only valid for use_item")
        return self


class Narration(BaseModel):
    """Public wording plus evidence IDs; these IDs are checked against retrieval."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list)


class WebActionPlan(BaseModel):
    """The existing Keeper planner's extended web action, never an effect.

    The graph translates this proposal into a tool DTO only after validating
    the currently public targets, methods, inventory and confirmation state.
    """

    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "look", "investigate", "careful_search", "observe", "inspect", "talk",
        "move", "take", "interact", "use_item", "drop", "give", "finish",
        "leave", "confirm_action", "rule_question", "question", "clarify", "unsupported",
    ]
    target_id: Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")] | None = None
    option_id: Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")] | None = None
    skill: str | None = Field(default=None, max_length=80)
    item_id: Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")] | None = None
    query: str | None = Field(default=None, max_length=500)
    question: str | None = Field(default=None, max_length=300)
    approach: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def consistent_web_action(self) -> "WebActionPlan":
        if self.intent == "rule_question" and not (self.query and self.query.strip()):
            raise ValueError("rule_question requires a nonempty query")
        if self.intent == "clarify" and not (self.question and self.question.strip()):
            raise ValueError("clarify requires a nonempty question")
        if self.intent in {"question", "rule_question", "clarify", "unsupported"}:
            if any(value is not None for value in (self.target_id, self.option_id, self.skill, self.item_id)):
                raise ValueError("information-only plans cannot contain a tool call")
        elif self.target_id is None:
            raise ValueError("tool proposals require an explicit current target")
        if self.intent in {"use_item", "give"} and self.item_id is None:
            raise ValueError("item use or transfer requires an explicit held item")
        return self
