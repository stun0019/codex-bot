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
    model_validator,
)

from ..models import (
    AgentOutput,
    TradeBias,
)


class RiskVerdict(
    StrEnum
):
    APPROVE = "approve"
    REDUCE = "reduce"
    REJECT = "reject"
    REVIEW = "review"


class RiskSeverity(
    StrEnum
):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(
    StrEnum
):
    ACCOUNT = "account"
    POSITION = "position"
    LEVERAGE = "leverage"
    STOP = "stop"
    REWARD = "reward"
    EXPOSURE = "exposure"
    DAILY_LOSS = "daily_loss"
    MARKET = "market"
    CHARTS = "charts"
    SENTIMENT = "sentiment"
    NEWS = "news"
    OTHER = "other"


class ProposedTrade(
    BaseModel
):
    symbol: str

    side: TradeBias

    entry_price: float = Field(
        gt=0.0,
    )

    current_price: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    stop_loss: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    take_profit: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    leverage: float = Field(
        default=1.0,
        ge=1.0,
        le=125.0,
    )

    notional_usdt: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    quantity: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    strategy: (
        str
        | None
    ) = None

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    @model_validator(
        mode="after"
    )
    def validate_side(
        self,
    ) -> "ProposedTrade":

        if self.side not in (
            TradeBias.LONG,
            TradeBias.SHORT,
        ):

            raise ValueError(
                (
                    "ProposedTrade.side "
                    "must be LONG or SHORT."
                )
            )

        return self


class OpenPosition(
    BaseModel
):
    symbol: str

    side: TradeBias

    notional_usdt: (
        float
        | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    quantity: (
        float
        | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    entry_price: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    current_price: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    leverage: float = Field(
        default=1.0,
        ge=1.0,
        le=125.0,
    )

    unrealized_pnl: (
        float
        | None
    ) = None

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class RiskLimits(
    BaseModel
):
    """
    Configurable advisory defaults.

    這些不是交易所硬限制，
    production 應由獨立 risk engine
    再執行真正 hard controls。
    """

    max_risk_per_trade_pct: float = Field(
        default=2.0,
        gt=0.0,
    )

    max_position_notional_pct: float = Field(
        default=25.0,
        gt=0.0,
    )

    max_symbol_exposure_pct: float = Field(
        default=30.0,
        gt=0.0,
    )

    max_total_exposure_pct: float = Field(
        default=100.0,
        gt=0.0,
    )

    max_leverage: float = Field(
        default=10.0,
        ge=1.0,
    )

    min_risk_reward: float = Field(
        default=1.5,
        gt=0.0,
    )

    max_stop_distance_pct: float = Field(
        default=8.0,
        gt=0.0,
    )

    max_daily_loss_pct: float = Field(
        default=5.0,
        gt=0.0,
    )

    min_free_balance_pct: float = Field(
        default=10.0,
        ge=0.0,
        lt=100.0,
    )


class RiskInput(
    BaseModel
):
    account_equity: (
        float
        | None
    ) = Field(
        default=None,
        gt=0.0,
    )

    available_balance: (
        float
        | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    daily_pnl: (
        float
        | None
    ) = None

    open_positions: list[
        OpenPosition
    ] = Field(
        default_factory=list
    )

    proposed_trade: (
        ProposedTrade
        | None
    ) = None

    risk_limits: RiskLimits = Field(
        default_factory=RiskLimits
    )

    charts_result: dict[
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

    news_result: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class RiskCheck(
    BaseModel
):
    name: str

    category: RiskCategory = (
        RiskCategory.OTHER
    )

    passed: bool

    severity: RiskSeverity = (
        RiskSeverity.MEDIUM
    )

    blocking: bool = False

    reason: str = ""

    value: Any | None = None

    limit: Any | None = None


class RiskMetrics(
    BaseModel
):
    notional_usdt: (
        float
        | None
    ) = None

    margin_required_usdt: (
        float
        | None
    ) = None

    stop_distance_pct: (
        float
        | None
    ) = None

    target_distance_pct: (
        float
        | None
    ) = None

    estimated_loss_usdt: (
        float
        | None
    ) = None

    estimated_reward_usdt: (
        float
        | None
    ) = None

    risk_pct_equity: (
        float
        | None
    ) = None

    risk_reward_ratio: (
        float
        | None
    ) = None

    position_exposure_pct: (
        float
        | None
    ) = None

    symbol_exposure_after_pct: (
        float
        | None
    ) = None

    total_exposure_before_pct: (
        float
        | None
    ) = None

    total_exposure_after_pct: (
        float
        | None
    ) = None

    daily_drawdown_pct: (
        float
        | None
    ) = None

    recommended_notional_usdt: (
        float
        | None
    ) = None

    overall_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    data_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class RiskSnapshot(
    BaseModel
):
    symbol: str

    verdict: RiskVerdict = (
        RiskVerdict.REVIEW
    )

    approved: bool = False

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    metrics: RiskMetrics = Field(
        default_factory=RiskMetrics
    )

    checks: list[
        RiskCheck
    ] = Field(
        default_factory=list
    )

    recommendations: list[
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


class RiskOutput(
    AgentOutput
):
    approved: bool = False

    verdict: RiskVerdict = (
        RiskVerdict.REVIEW
    )

    checks: list[
        RiskCheck
    ] = Field(
        default_factory=list
    )

    metrics: RiskMetrics = Field(
        default_factory=RiskMetrics
    )

    recommendations: list[
        str
    ] = Field(
        default_factory=list
    )

    proposed_position_size: (
        float
        | None
    ) = None

    estimated_loss: (
        float
        | None
    ) = None

    estimated_reward: (
        float
        | None
    ) = None
