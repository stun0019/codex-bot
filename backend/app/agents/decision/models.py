from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from enum import StrEnum

from typing import Any

from pydantic import (
    BaseModel,
    Field,
)

from ..models import (
    AgentOutput,
    TradeBias,
)

from ..risk.models import (
    ProposedTrade,
)


class DecisionGateStatus(
    StrEnum
):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_AVAILABLE = "not_available"


class DecisionGate(
    BaseModel
):
    name: str

    status: DecisionGateStatus

    blocking: bool = False

    reason: str = ""

    value: Any | None = None


class DecisionMetrics(
    BaseModel
):
    directional_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

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

    consensus_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    disagreement_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    data_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    charts_score: (
        float
        | None
    ) = Field(
        default=None,
        ge=-1.0,
        le=1.0,
    )

    sentiment_score: (
        float
        | None
    ) = Field(
        default=None,
        ge=-1.0,
        le=1.0,
    )

    news_score: (
        float
        | None
    ) = Field(
        default=None,
        ge=-1.0,
        le=1.0,
    )

    scout_opportunity_score: (
        float
        | None
    ) = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class DecisionInput(
    BaseModel
):
    scout_result: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    news_result: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    sentiment_result: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    charts_result: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    risk_result: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    proposed_trade: (
        ProposedTrade
        | None
    ) = None

    require_risk_approval: bool = True

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class TradeDecision(
    BaseModel
):
    action: TradeBias = (
        TradeBias.WAIT
    )

    directional_bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    symbol: str

    entry_price: (
        float
        | None
    ) = None

    stop_loss: (
        float
        | None
    ) = None

    take_profit: (
        float
        | None
    ) = None

    position_size: (
        float
        | None
    ) = None

    position_size_unit: (
        str
        | None
    ) = None

    strategy: (
        str
        | None
    ) = None

    reasoning: list[
        str
    ] = Field(
        default_factory=list
    )

    gates: list[
        DecisionGate
    ] = Field(
        default_factory=list
    )


class DecisionSnapshot(
    BaseModel
):
    symbol: str

    action: TradeBias = (
        TradeBias.WAIT
    )

    directional_bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    risk_approved: bool = False

    metrics: DecisionMetrics = Field(
        default_factory=DecisionMetrics
    )

    gates: list[
        DecisionGate
    ] = Field(
        default_factory=list
    )

    reasoning: list[
        str
    ] = Field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    created_at: datetime = Field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )


class DecisionOutput(
    AgentOutput
):
    directional_bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    risk_approved: bool = False

    metrics: DecisionMetrics = Field(
        default_factory=DecisionMetrics
    )

    gates: list[
        DecisionGate
    ] = Field(
        default_factory=list
    )

    decision: TradeDecision
