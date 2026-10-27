from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    SCOUT = "scout"
    NEWS = "news"
    SENTIMENT = "sentiment"
    CHARTS = "charts"
    RISK = "risk"
    DECISION = "decision"


class AgentStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


class TradeBias(StrEnum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    WAIT = "wait"


class EvidenceItem(BaseModel):
    source: str
    description: str
    value: Any | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MarketContext(BaseModel):
    symbol: str

    exchange: str = "OKX"

    market_type: str = "swap"

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    timeframes: list[str] = Field(default_factory=list)

    market_data: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    agent: AgentName

    status: AgentStatus = AgentStatus.SUCCESS

    symbol: str

    bias: TradeBias = TradeBias.NEUTRAL

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    summary: str = ""

    evidence: list[EvidenceItem] = Field(default_factory=list)

    data: dict[str, Any] = Field(default_factory=dict)

    errors: list[str] = Field(default_factory=list)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
