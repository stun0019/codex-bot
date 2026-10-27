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


class TechnicalSignalType(
    StrEnum
):
    """
    技術訊號類型。
    """

    TREND = "trend"

    MOMENTUM = "momentum"

    VOLATILITY = "volatility"

    VOLUME = "volume"

    STRUCTURE = "structure"

    BREAKOUT = "breakout"

    SUPPORT_RESISTANCE = (
        "support_resistance"
    )

    OTHER = "other"


class TrendRegime(
    StrEnum
):
    """
    技術趨勢狀態。
    """

    STRONG_UPTREND = (
        "strong_uptrend"
    )

    UPTREND = "uptrend"

    RANGE = "range"

    DOWNTREND = "downtrend"

    STRONG_DOWNTREND = (
        "strong_downtrend"
    )

    UNKNOWN = "unknown"


class VolatilityRegime(
    StrEnum
):
    """
    波動率狀態。
    """

    HIGH = "high"

    NORMAL = "normal"

    LOW = "low"

    UNKNOWN = "unknown"


class CandleData(
    BaseModel
):
    """
    CHARTS 統一 K 線格式。

    不綁定 OKX。

    未來：

        Binance
        BingX
        Bybit
        Backtest DB

    都可以先轉成 CandleData。
    """

    timestamp: datetime

    open: float = Field(
        gt=0.0,
    )

    high: float = Field(
        gt=0.0,
    )

    low: float = Field(
        gt=0.0,
    )

    close: float = Field(
        gt=0.0,
    )

    volume: float = Field(
        default=0.0,
        ge=0.0,
    )

    volume_currency: (
        float
        | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    volume_quote: (
        float
        | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    confirmed: bool = True

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    @model_validator(
        mode="after"
    )
    def validate_ohlc(
        self,
    ) -> "CandleData":
        """
        基本 OHLC integrity。

        high 必須 >= open/close/low
        low 必須 <= open/close/high
        """

        highest_body = max(
            self.open,
            self.close,
            self.low,
        )

        lowest_body = min(
            self.open,
            self.close,
            self.high,
        )

        if (
            self.high
            <
            highest_body
        ):

            raise ValueError(
                (
                    "Candle high "
                    "cannot be below "
                    "open/close/low."
                )
            )

        if (
            self.low
            >
            lowest_body
        ):

            raise ValueError(
                (
                    "Candle low "
                    "cannot be above "
                    "open/close/high."
                )
            )

        return self


class TechnicalSignal(
    BaseModel
):
    """
    單一技術分析 signal。

    score：

        -1.0 = 強烈偏空
         0.0 = 中性
        +1.0 = 強烈偏多

    strength：

        signal 本身的強度。

    confidence：

        signal 的可信度。

    注意：

    direction / score 都只是
    技術面觀察，

    不是交易指令。
    """

    signal_type: (
        TechnicalSignalType
    )

    name: str

    timeframe: (
        str
        | None
    ) = None

    direction: TradeBias = (
        TradeBias.NEUTRAL
    )

    score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    value: (
        Any
        | None
    ) = None

    description: str = ""

    details: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    timestamp: datetime = Field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )


class TimeframeAnalysis(
    BaseModel
):
    """
    單一 timeframe 的完整
    technical analysis。

    例如：

        15m
        1H
        4H
        1D
    """

    timeframe: str

    candle_count: int = Field(
        default=0,
        ge=0,
    )

    bias: TradeBias = (
        TradeBias.NEUTRAL
    )

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

    trend_regime: TrendRegime = (
        TrendRegime.UNKNOWN
    )

    volatility_regime: (
        VolatilityRegime
    ) = (
        VolatilityRegime.UNKNOWN
    )

    indicators: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    market_structure: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    signals: list[
        TechnicalSignal
    ] = Field(
        default_factory=list
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


class ChartsInput(
    BaseModel
):
    """
    CHARTS Agent 輸入。

    candles：

        key = timeframe

        value = normalized CandleData

    例如：

        {
            "15m": [...],
            "1H": [...],
            "4H": [...],
            "1D": [...]
        }

    indicators：

        允許外部系統預先提供
        額外 indicators。

    structure_data：

        允許未來 order-flow、
        market-profile、
        custom strategy
        提供額外 structure。
    """

    candles: dict[
        str,
        list[
            CandleData
        ],
    ] = Field(
        default_factory=dict
    )

    indicators: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    structure_data: dict[
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


class ChartsSnapshot(
    BaseModel
):
    """
    CHARTS Analyzer 的完整 snapshot。

    可供：

        Agent
        DECISION
        database
        dashboard
        backtest
    """

    symbol: str

    bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    composite_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    trend_regime: TrendRegime = (
        TrendRegime.UNKNOWN
    )

    volatility_regime: (
        VolatilityRegime
    ) = (
        VolatilityRegime.UNKNOWN
    )

    primary_timeframe: (
        str
        | None
    ) = None

    timeframe_analyses: dict[
        str,
        TimeframeAnalysis,
    ] = Field(
        default_factory=dict
    )

    signals: list[
        TechnicalSignal
    ] = Field(
        default_factory=list
    )

    market_structure: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
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


class ChartsOutput(
    AgentOutput
):
    """
    CHARTS Agent 最終輸出。

    AgentOutput 已提供：

        agent
        status
        symbol
        bias
        confidence
        summary
        evidence
        data
        errors

    CHARTS 額外輸出：

        technical signals
        timeframe analyses
        market structure
        trend regime
        volatility regime
    """

    composite_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
    )

    trend_regime: TrendRegime = (
        TrendRegime.UNKNOWN
    )

    volatility_regime: (
        VolatilityRegime
    ) = (
        VolatilityRegime.UNKNOWN
    )

    primary_timeframe: (
        str
        | None
    ) = None

    signals: list[
        TechnicalSignal
    ] = Field(
        default_factory=list
    )

    timeframe_analyses: dict[
        str,
        TimeframeAnalysis,
    ] = Field(
        default_factory=dict
    )

    market_structure: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
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
