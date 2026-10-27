from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import AgentOutput


class ScoutInput(BaseModel):
    symbols: list[str] = Field(default_factory=list)

    ticker_data: dict[str, Any] = Field(default_factory=dict)

    volume_data: dict[str, Any] = Field(default_factory=dict)

    volatility_data: dict[str, Any] = Field(default_factory=dict)

    liquidity_data: dict[str, Any] = Field(default_factory=dict)


class ScoutCandidate(BaseModel):
    symbol: str

    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    reasons: list[str] = Field(default_factory=list)

    metrics: dict[str, Any] = Field(default_factory=dict)


class ScoutOutput(AgentOutput):
    candidates: list[ScoutCandidate] = Field(
        default_factory=list
    )
