from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
)

from ..agents.charts import (
    TradePlan,
)

from ..agents.models import (
    TradeBias,
)

from ..agents.risk.models import (
    OpenPosition,
    RiskLimits,
)


class OpportunityStatus(
    StrEnum
):
    ACTIONABLE = "actionable"
    WAIT = "wait"
    ERROR = "error"


class OpportunityScanInput(
    BaseModel
):
    """
    RUN ALL account state.

    這裡不要求使用者提供：

        Symbol
        Side
        Entry
        Stop
        Target

    因為那些由系統自己找。

    只需要帳戶風險資料。
    """

    account_equity: float = Field(
        gt=0.0,
    )

    available_balance: float = Field(
        ge=0.0,
    )

    daily_pnl: float = 0.0

    leverage: float = Field(
        default=3.0,
        ge=1.0,
        le=125.0,
    )

    open_positions: list[
        OpenPosition
    ] = Field(
        default_factory=list
    )

    risk_limits: RiskLimits = Field(
        default_factory=RiskLimits
    )

    max_candidates: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    max_concurrency: int = Field(
        default=3,
        ge=1,
        le=6,
    )

    include_news: bool = True

    minimum_scout_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class OpportunityResult(
    BaseModel
):
    symbol: str

    status: OpportunityStatus

    scout_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

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

    rank_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    trade_plan: (
        TradePlan
        | None
    ) = None

    risk_verdict: (
        str
        | None
    ) = None

    risk_approved: bool = False

    recommended_notional_usdt: (
        float
        | None
    ) = None

    estimated_loss_usdt: (
        float
        | None
    ) = None

    risk_pct_equity: (
        float
        | None
    ) = None

    reasons: list[
        str
    ] = Field(
        default_factory=list
    )

    errors: list[
        str
    ] = Field(
        default_factory=list
    )


class OpportunitiesOutput(
    BaseModel
):
    status: str = "success"

    scanned_count: int = 0

    evaluated_count: int = 0

    actionable_count: int = 0

    opportunities: list[
        OpportunityResult
    ] = Field(
        default_factory=list
    )

    evaluated: list[
        OpportunityResult
    ] = Field(
        default_factory=list
    )

    errors: list[
        str
    ] = Field(
        default_factory=list
    )

    created_at: datetime = Field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )
