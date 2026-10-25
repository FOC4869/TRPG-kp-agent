"""Storage and tool-boundary data, independent of models and story execution."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GameError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def digest(value) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class ToolCall(BaseModel):
    """A validated request from our Keeper to a deterministic tool."""
    model_config = ConfigDict(extra="forbid", strict=True)
    name: Literal["move", "observe", "talk", "take", "inspect", "interact", "finish",
                  "use_item", "drop", "give", "confirm_action"]
    target: str = Field(min_length=1, max_length=80)
    option: str | None = None
    skill: str | None = None
    item: str | None = None
    approach: str = Field(default="", max_length=500)


class ExecutionRequest(BaseModel):
    """Persist a tool request or an explicitly non-executing response route."""
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["tool", "question", "clarify", "unsupported"]
    tool: ToolCall | None = None

    @model_validator(mode="after")
    def require_tool_only_for_execution(self):
        if self.kind == "tool" and self.tool is None:
            raise ValueError("An execution request requires one tool call")
        if self.kind != "tool" and self.tool is not None:
            raise ValueError("A non-execution request cannot contain a tool call")
        return self
