from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import AgentOutput


class ChartsInput(BaseModel):
    candles: dict[
        str,
        list[dict[str, Any]],
    ] = Field(default_factory=dict)

    indicators: dict[str, Any] = Field(
        default_factory=dict
    )

    structure_data: dict[str, Any] = Field(
        default_factory=dict
    )


class TechnicalSignal(BaseModel):
    name: str

    timeframe: str | None = None

    direction: str | None = None

    strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    details: dict[str, Any] = Field(
        default_factory=dict
    )


class ChartsOutput(AgentOutput):
    signals: list[TechnicalSignal] = Field(
        default_factory=list
    )

    market_structure: dict[str, Any] = Field(
        default_factory=dict
    )
