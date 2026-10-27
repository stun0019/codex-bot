from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import (
    AgentOutput,
    TradeBias,
)


class DecisionInput(BaseModel):
    scout_result: dict[str, Any] = Field(
        default_factory=dict
    )

    news_result: dict[str, Any] = Field(
        default_factory=dict
    )

    sentiment_result: dict[str, Any] = Field(
        default_factory=dict
    )

    charts_result: dict[str, Any] = Field(
        default_factory=dict
    )

    risk_result: dict[str, Any] = Field(
        default_factory=dict
    )


class TradeDecision(BaseModel):
    action: TradeBias = TradeBias.WAIT

    symbol: str

    entry_price: float | None = None

    stop_loss: float | None = None

    take_profit: float | None = None

    position_size: float | None = None

    strategy: str | None = None

    reasoning: list[str] = Field(
        default_factory=list
    )


class DecisionOutput(AgentOutput):
    decision: TradeDecision
