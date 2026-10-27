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


class SentimentSource(
    StrEnum
):
    """
    SENTIMENT 可使用的資料來源類型。
    """

    FUNDING = "funding"

    OPEN_INTEREST = (
        "open_interest"
    )

    LONG_SHORT_RATIO = (
        "long_short_ratio"
    )

    SOCIAL = "social"

    LIQUIDATION = "liquidation"

    MARKET_ACTIVITY = (
        "market_activity"
    )

    OTHER = "other"


class SentimentRegime(
    StrEnum
):
    """
    整體市場情緒狀態。

    注意：

    EXTREME_BULLISH 不代表應該 LONG。

    極端多頭情緒也可能代表：

        long crowded
        squeeze risk
        reversal risk
    """

    EXTREME_BULLISH = (
        "extreme_bullish"
    )

    BULLISH = "bullish"

    NEUTRAL = "neutral"

    BEARISH = "bearish"

    EXTREME_BEARISH = (
        "extreme_bearish"
    )


class CrowdingSide(
    StrEnum
):
    """
    市場擁擠方向。
    """

    LONG = "long"

    SHORT = "short"

    BALANCED = "balanced"

    UNKNOWN = "unknown"


class SentimentSignal(
    BaseModel
):
    """
    單一情緒 / positioning 訊號。

    score:

        -1.0 = 強烈偏空
         0.0 = 中性
        +1.0 = 強烈偏多

    confidence:

        此 signal 的可信程度。

    crowding_score:

        0.0 = 無明顯擁擠
        1.0 = 極端擁擠

    directional_bias:

        這個 signal 本身的方向性。

    注意：

    directional_bias 不是交易指令。
    """

    source: SentimentSource

    name: str

    score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    crowding_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    directional_bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    value: Any | None = None

    description: str = ""

    timestamp: datetime = Field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class SentimentInput(
    BaseModel
):
    """
    SENTIMENT Agent 輸入。

    原始資料仍使用 dict，
    讓未來不同交易所 / source
    可以先送入 Analyzer 再正規化。

    signals:

        允許 service 或其他來源
        直接提供已正規化 signal。
    """

    social_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    funding_rate_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    open_interest_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    long_short_ratio_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    liquidation_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    market_activity_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    signals: list[
        SentimentSignal
    ] = Field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class SentimentMetrics(
    BaseModel
):
    """
    SENTIMENT 最終量化結果。

    composite_score:

        -1.0 ~ +1.0

        -1.0 = 強烈偏空情緒
         0.0 = 中性
        +1.0 = 強烈偏多情緒

    crowding_score:

        0.0 ~ 1.0

        越高代表 positioning
        越集中 / 越極端。

    data_quality_score:

        可用資料完整度與可信程度。

    disagreement_score:

        不同 sentiment signals
        互相矛盾的程度。

        例如：

        funding extremely bullish
        但
        social extremely bearish

        disagreement 就應該提高。
    """

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

    composite_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    crowding_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    data_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    disagreement_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    signal_count: int = Field(
        default=0,
        ge=0,
    )


class SentimentSnapshot(
    BaseModel
):
    """
    SENTIMENT 對單一市場的完整 snapshot。

    可供：

    - logging
    - database
    - dashboard
    - DECISION Agent
    - backtest

    使用。
    """

    symbol: str

    regime: SentimentRegime = (
        SentimentRegime.NEUTRAL
    )

    crowding_side: CrowdingSide = (
        CrowdingSide.UNKNOWN
    )

    metrics: SentimentMetrics = Field(
        default_factory=(
            SentimentMetrics
        )
    )

    signals: list[
        SentimentSignal
    ] = Field(
        default_factory=list
    )

    timestamp: datetime = Field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class SentimentOutput(
    AgentOutput
):
    """
    SENTIMENT Agent 最終輸出。

    AgentOutput 已包含：

        agent
        status
        symbol
        bias
        confidence
        summary
        evidence
        data
        errors
        created_at

    SENTIMENT 額外提供：

        regime
        crowding_side
        metrics
        signals
    """

    regime: SentimentRegime = (
        SentimentRegime.NEUTRAL
    )

    crowding_side: CrowdingSide = (
        CrowdingSide.UNKNOWN
    )

    metrics: SentimentMetrics = Field(
        default_factory=(
            SentimentMetrics
        )
    )

    signals: list[
        SentimentSignal
    ] = Field(
        default_factory=list
    )
