from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import AgentOutput


class SentimentInput(BaseModel):
    social_data: dict[str, Any] = Field(
        default_factory=dict
    )

    funding_rate_data: dict[str, Any] = Field(
        default_factory=dict
    )

    open_interest_data: dict[str, Any] = Field(
        default_factory=dict
    )

    long_short_ratio_data: dict[str, Any] = Field(
        default_factory=dict
    )


class SentimentMetrics(BaseModel):
    bullish_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    bearish_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    neutral_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    crowding_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class SentimentOutput(AgentOutput):
    metrics: SentimentMetrics = Field(
        default_factory=SentimentMetrics
    )
