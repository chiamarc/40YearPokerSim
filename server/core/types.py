from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlayerLimits(BaseModel):
    min: int = Field(ge=1)
    max: int = Field(ge=1)


class ModuleConfig(BaseModel):
    id: str
    name: str
    description: str
    player_limits: PlayerLimits
    ui_schema: dict[str, Any] = Field(default_factory=dict)
    betting_rules: dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    module_id: str
    player_count: int


class SessionState(BaseModel):
    id: str
    module_id: str
    player_count: int
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionRequest(BaseModel):
    player_index: int
    action: str
    amount: float | None = None
