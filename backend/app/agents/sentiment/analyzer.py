from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Any

from ..models import TradeBias

from .models import (
    CrowdingSide,
    SentimentInput,
    SentimentMetrics,
    SentimentRegime,
    SentimentSignal,
    SentimentSnapshot,
    SentimentSource,
)


@dataclass(slots=True)
class SentimentAnalyzerConfig:
    """
    SENTIMENT deterministic analyzer 設定。

    所有 threshold 都只是 V1 預設值。

    未來可以：

    - backtest 校準
    - per-symbol calibration
    - per-exchange calibration
    - volatility-adjusted thresholds
    """

    # ---------------------------------
    # Funding
    # ---------------------------------

    funding_soft_threshold: float = 0.0001

    funding_strong_threshold: float = 0.0005

    funding_extreme_threshold: float = 0.0010

    # ---------------------------------
    # Open Interest change %
    # ---------------------------------

    oi_soft_change_pct: float = 2.0

    oi_strong_change_pct: float = 5.0

    oi_extreme_change_pct: float = 10.0

    # ---------------------------------
    # Long / Short ratio
    # ---------------------------------

    long_short_soft_high: float = 1.10

    long_short_strong_high: float = 1.30

    long_short_extreme_high: float = 1.60

    long_short_soft_low: float = 0.90

    long_short_strong_low: float = 0.75

    long_short_extreme_low: float = 0.60

    # ---------------------------------
    # Social sentiment
    #
    # 預期 normalized score:
    #
    # -1.0 = bearish
    #  0.0 = neutral
    # +1.0 = bullish
    # ---------------------------------

    social_soft_threshold: float = 0.20

    social_strong_threshold: float = 0.50

    social_extreme_threshold: float = 0.75

    # ---------------------------------
    # Liquidation imbalance
    #
    # long / short liquidation USD
    # ---------------------------------

    liquidation_soft_ratio: float = 1.50

    liquidation_strong_ratio: float = 2.50

    liquidation_extreme_ratio: float = 4.00

    # ---------------------------------
    # Market activity
    #
    # price_change_pct
    # ---------------------------------

    activity_soft_pct: float = 1.0

    activity_strong_pct: float = 3.0

    activity_extreme_pct: float = 6.0

    # ---------------------------------
    # Composite regime
    # ---------------------------------

    bullish_threshold: float = 0.20

    extreme_bullish_threshold: float = 0.60

    bearish_threshold: float = -0.20

    extreme_bearish_threshold: float = -0.60

    # ---------------------------------
    # Crowding
    # ---------------------------------

    crowding_side_threshold: float = 0.25

    # ---------------------------------
    # Signal weights
    # ---------------------------------

    funding_weight: float = 0.24

    open_interest_weight: float = 0.17

    long_short_weight: float = 0.24

    social_weight: float = 0.15

    liquidation_weight: float = 0.12

    market_activity_weight: float = 0.08


class SentimentAnalyzer:
    """
    SENTIMENT deterministic engine。

    Pipeline:

        Raw sentiment data
            ↓
        Normalize
            ↓
        SentimentSignal[]
            ↓
        Weighted aggregation
            ↓
        SentimentMetrics
            ↓
        SentimentSnapshot

    此 Analyzer 不呼叫 LLM。

    目的：

    - 統一 heterogeneous sentiment data
    - 避免單一指標直接決定方向
    - 分離 sentiment 與 crowding
    - 提供可重現 deterministic baseline
    """

    def __init__(
        self,
        config: SentimentAnalyzerConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else SentimentAnalyzerConfig()
        )

    def analyze(
        self,
        symbol: str,
        payload: SentimentInput,
    ) -> SentimentSnapshot:

        signals: list[
            SentimentSignal
        ] = []

        # 已經由 source/service
        # 正規化完成的 signal
        signals.extend(
            payload.signals
        )

        funding_signal = (
            self._analyze_funding(
                payload.funding_rate_data
            )
        )

        if funding_signal is not None:

            signals.append(
                funding_signal
            )

        oi_signal = (
            self._analyze_open_interest(
                payload.open_interest_data,
                payload.market_activity_data,
            )
        )

        if oi_signal is not None:

            signals.append(
                oi_signal
            )

        long_short_signal = (
            self._analyze_long_short_ratio(
                payload.long_short_ratio_data
            )
        )

        if long_short_signal is not None:

            signals.append(
                long_short_signal
            )

        social_signal = (
            self._analyze_social(
                payload.social_data
            )
        )

        if social_signal is not None:

            signals.append(
                social_signal
            )

        liquidation_signal = (
            self._analyze_liquidations(
                payload.liquidation_data
            )
        )

        if liquidation_signal is not None:

            signals.append(
                liquidation_signal
            )

        activity_signal = (
            self._analyze_market_activity(
                payload.market_activity_data
            )
        )

        if activity_signal is not None:

            signals.append(
                activity_signal
            )

        metrics = (
            self._build_metrics(
                signals
            )
        )

        regime = (
            self._resolve_regime(
                metrics.composite_score
            )
        )

        crowding_side = (
            self._resolve_crowding_side(
                signals
            )
        )

        return SentimentSnapshot(
            symbol=symbol,

            regime=regime,

            crowding_side=(
                crowding_side
            ),

            metrics=metrics,

            signals=signals,

            metadata={
                "deterministic_analysis":
                    True,

                "signal_count":
                    len(
                        signals
                    ),

                "sources": [
                    signal.source.value
                    for signal
                    in signals
                ],
            },
        )

    # =================================
    # Funding
    # =================================

    def _analyze_funding(
        self,
        data: dict[
            str,
            Any,
        ],
    ) -> SentimentSignal | None:

        value = self._extract_float(
            data,
            (
                "funding_rate",
                "fundingRate",
                "rate",
                "current",
                "value",
            ),
        )

        if value is None:

            return None

        magnitude = abs(
            value
        )

        if (
            magnitude
            >=
            self.config
            .funding_extreme_threshold
        ):

            crowding = 1.0

            confidence = 0.95

        elif (
            magnitude
            >=
            self.config
            .funding_strong_threshold
        ):

            crowding = 0.80

            confidence = 0.90

        elif (
            magnitude
            >=
            self.config
            .funding_soft_threshold
        ):

            crowding = 0.50

            confidence = 0.80

        else:

            crowding = self._clamp01(
                magnitude
                /
                max(
                    self.config
                    .funding_soft_threshold,
                    1e-12,
                )
                *
                0.30
            )

            confidence = 0.70

        # Funding 正值：
        # 市場 positioning 偏多。
        #
        # Funding 負值：
        # 市場 positioning 偏空。
        #
        # 注意這不是 contrarian reversal signal。
        score = self._signed_scale(
            value,
            self.config
            .funding_extreme_threshold,
        )

        bias = self._score_bias(
            score
        )

        description = (
            "Positive funding indicates "
            "long-side positioning."
            if value > 0
            else
            "Negative funding indicates "
            "short-side positioning."
            if value < 0
            else
            "Funding is neutral."
        )

        return SentimentSignal(
            source=(
                SentimentSource.FUNDING
            ),

            name="funding_rate",

            score=score,

            confidence=confidence,

            crowding_score=(
                crowding
            ),

            directional_bias=bias,

            value=value,

            description=description,

            metadata={
                "raw":
                    dict(
                        data
                    ),
            },
        )

    # =================================
    # Open Interest
    # =================================

    def _analyze_open_interest(
        self,
        data: dict[
            str,
            Any,
        ],
        market_activity: dict[
            str,
            Any,
        ],
    ) -> SentimentSignal | None:

        change_pct = (
            self._extract_float(
                data,
                (
                    "change_pct",
                    "changePct",
                    "oi_change_pct",
                    "open_interest_change_pct",
                    "pct_change",
                ),
            )
        )

        if change_pct is None:

            current = (
                self._extract_float(
                    data,
                    (
                        "current",
                        "open_interest",
                        "openInterest",
                        "oi",
                    ),
                )
            )

            previous = (
                self._extract_float(
                    data,
                    (
                        "previous",
                        "previous_open_interest",
                        "previousOpenInterest",
                        "previous_oi",
                    ),
                )
            )

            if (
                current is not None
                and previous is not None
                and previous != 0
            ):

                change_pct = (
                    (
                        current
                        -
                        previous
                    )
                    /
                    previous
                    *
                    100
                )

        if change_pct is None:

            return None

        price_change = (
            self._extract_float(
                market_activity,
                (
                    "price_change_pct",
                    "priceChangePct",
                    "change_pct",
                    "changePct",
                    "return_pct",
                ),
            )
        )

        magnitude = abs(
            change_pct
        )

        confidence = (
            0.90
            if (
                magnitude
                >=
                self.config
                .oi_extreme_change_pct
            )
            else
            0.85
            if (
                magnitude
                >=
                self.config
                .oi_strong_change_pct
            )
            else
            0.75
        )

        crowding = (
            self._magnitude_scale(
                change_pct,
                self.config
                .oi_extreme_change_pct,
            )
        )

        # OI 本身沒有 bullish / bearish。
        #
        # 必須結合 price：
        #
        # Price ↑ + OI ↑
        #     新多部位 / 趨勢參與增加
        #
        # Price ↓ + OI ↑
        #     新空部位 / bearish positioning
        #
        # OI ↓
        #     position unwinding，方向可信度降低

        if (
            price_change is None
        ):

            score = 0.0

            bias = (
                TradeBias.NEUTRAL
            )

            description = (
                "Open interest changed, "
                "but price direction is "
                "unavailable."
            )

        elif (
            change_pct > 0
            and price_change > 0
        ):

            score = (
                self._magnitude_scale(
                    change_pct,
                    self.config
                    .oi_extreme_change_pct,
                )
                *
                self._sign(
                    price_change
                )
            )

            bias = (
                self._score_bias(
                    score
                )
            )

            description = (
                "Price and open interest "
                "are rising together."
            )

        elif (
            change_pct > 0
            and price_change < 0
        ):

            score = -(
                self._magnitude_scale(
                    change_pct,
                    self.config
                    .oi_extreme_change_pct,
                )
            )

            bias = (
                self._score_bias(
                    score
                )
            )

            description = (
                "Price is falling while "
                "open interest is rising."
            )

        else:

            score = (
                self._signed_scale(
                    price_change,
                    self.config
                    .activity_extreme_pct,
                )
                *
                0.35
            )

            confidence *= 0.70

            crowding *= 0.45

            bias = (
                self._score_bias(
                    score
                )
            )

            description = (
                "Open interest is declining, "
                "suggesting position unwinding."
            )

        return SentimentSignal(
            source=(
                SentimentSource
                .OPEN_INTEREST
            ),

            name=(
                "open_interest_change"
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            confidence=(
                self._clamp01(
                    confidence
                )
            ),

            crowding_score=(
                self._clamp01(
                    crowding
                )
            ),

            directional_bias=bias,

            value={
                "change_pct":
                    change_pct,

                "price_change_pct":
                    price_change,
            },

            description=description,

            metadata={
                "raw":
                    dict(
                        data
                    ),
            },
        )

    # =================================
    # Long / Short ratio
    # =================================

    def _analyze_long_short_ratio(
        self,
        data: dict[
            str,
            Any,
        ],
    ) -> SentimentSignal | None:

        ratio = (
            self._extract_float(
                data,
                (
                    "ratio",
                    "long_short_ratio",
                    "longShortRatio",
                    "longShortAccountRatio",
                    "value",
                ),
            )
        )

        if ratio is None:

            long_value = (
                self._extract_float(
                    data,
                    (
                        "long",
                        "long_ratio",
                        "longRatio",
                    ),
                )
            )

            short_value = (
                self._extract_float(
                    data,
                    (
                        "short",
                        "short_ratio",
                        "shortRatio",
                    ),
                )
            )

            if (
                long_value is not None
                and short_value is not None
                and short_value > 0
            ):

                ratio = (
                    long_value
                    /
                    short_value
                )

        if (
            ratio is None
            or ratio <= 0
        ):

            return None

        if (
            ratio
            >=
            self.config
            .long_short_extreme_high
        ):

            score = 1.0

            crowding = 1.0

            confidence = 0.90

        elif (
            ratio
            >=
            self.config
            .long_short_strong_high
        ):

            score = 0.70

            crowding = 0.80

            confidence = 0.85

        elif (
            ratio
            >=
            self.config
            .long_short_soft_high
        ):

            score = 0.35

            crowding = 0.50

            confidence = 0.78

        elif (
            ratio
            <=
            self.config
            .long_short_extreme_low
        ):

            score = -1.0

            crowding = 1.0

            confidence = 0.90

        elif (
            ratio
            <=
            self.config
            .long_short_strong_low
        ):

            score = -0.70

            crowding = 0.80

            confidence = 0.85

        elif (
            ratio
            <=
            self.config
            .long_short_soft_low
        ):

            score = -0.35

            crowding = 0.50

            confidence = 0.78

        else:

            distance = abs(
                ratio - 1.0
            )

            score = (
                self._clamp_signed(
                    ratio - 1.0
                )
            )

            crowding = (
                self._clamp01(
                    distance
                    /
                    0.10
                    *
                    0.25
                )
            )

            confidence = 0.70

        return SentimentSignal(
            source=(
                SentimentSource
                .LONG_SHORT_RATIO
            ),

            name=(
                "long_short_ratio"
            ),

            score=score,

            confidence=confidence,

            crowding_score=(
                crowding
            ),

            directional_bias=(
                self._score_bias(
                    score
                )
            ),

            value=ratio,

            description=(
                "Long positioning exceeds "
                "short positioning."
                if ratio > 1
                else
                "Short positioning exceeds "
                "long positioning."
                if ratio < 1
                else
                "Long and short positioning "
                "are balanced."
            ),

            metadata={
                "raw":
                    dict(
                        data
                    ),
            },
        )

    # =================================
    # Social
    # =================================

    def _analyze_social(
        self,
        data: dict[
            str,
            Any,
        ],
    ) -> SentimentSignal | None:

        score = (
            self._extract_float(
                data,
                (
                    "score",
                    "sentiment_score",
                    "sentimentScore",
                    "compound",
                    "normalized_score",
                    "value",
                ),
            )
        )

        if score is None:

            bullish = (
                self._extract_float(
                    data,
                    (
                        "bullish",
                        "bullish_ratio",
                        "positive",
                    ),
                )
            )

            bearish = (
                self._extract_float(
                    data,
                    (
                        "bearish",
                        "bearish_ratio",
                        "negative",
                    ),
                )
            )

            if (
                bullish is not None
                and bearish is not None
            ):

                total = (
                    bullish
                    +
                    bearish
                )

                if total > 0:

                    score = (
                        bullish
                        -
                        bearish
                    ) / total

        if score is None:

            return None

        # 如果 source 給的是 -100~100，
        # 做基本 normalization。
        if abs(
            score
        ) > 1:

            if abs(
                score
            ) <= 100:

                score /= 100

        score = (
            self._clamp_signed(
                score
            )
        )

        magnitude = abs(
            score
        )

        if (
            magnitude
            >=
            self.config
            .social_extreme_threshold
        ):

            confidence = 0.80

            crowding = 0.85

        elif (
            magnitude
            >=
            self.config
            .social_strong_threshold
        ):

            confidence = 0.75

            crowding = 0.65

        elif (
            magnitude
            >=
            self.config
            .social_soft_threshold
        ):

            confidence = 0.68

            crowding = 0.35

        else:

            confidence = 0.60

            crowding = 0.10

        sample_size = (
            self._extract_float(
                data,
                (
                    "sample_size",
                    "sampleSize",
                    "mentions",
                    "count",
                ),
            )
        )

        if (
            sample_size is not None
            and sample_size > 0
        ):

            sample_factor = min(
                1.0,
                math.log10(
                    sample_size + 1
                )
                /
                4.0,
            )

            confidence = (
                confidence
                *
                (
                    0.65
                    +
                    0.35
                    *
                    sample_factor
                )
            )

        return SentimentSignal(
            source=(
                SentimentSource.SOCIAL
            ),

            name=(
                "social_sentiment"
            ),

            score=score,

            confidence=(
                self._clamp01(
                    confidence
                )
            ),

            crowding_score=(
                crowding
            ),

            directional_bias=(
                self._score_bias(
                    score
                )
            ),

            value=score,

            description=(
                "Social sentiment is bullish."
                if score > 0.10
                else
                "Social sentiment is bearish."
                if score < -0.10
                else
                "Social sentiment is neutral."
            ),

            metadata={
                "sample_size":
                    sample_size,

                "raw":
                    dict(
                        data
                    ),
            },
        )

    # =================================
    # Liquidations
    # =================================

    def _analyze_liquidations(
        self,
        data: dict[
            str,
            Any,
        ],
    ) -> SentimentSignal | None:

        long_liquidations = (
            self._extract_float(
                data,
                (
                    "long_liquidations",
                    "longLiquidations",
                    "long_usd",
                    "longUsd",
                    "long",
                ),
            )
        )

        short_liquidations = (
            self._extract_float(
                data,
                (
                    "short_liquidations",
                    "shortLiquidations",
                    "short_usd",
                    "shortUsd",
                    "short",
                ),
            )
        )

        if (
            long_liquidations is None
            or short_liquidations is None
        ):

            return None

        long_liquidations = max(
            0.0,
            long_liquidations,
        )

        short_liquidations = max(
            0.0,
            short_liquidations,
        )

        total = (
            long_liquidations
            +
            short_liquidations
        )

        if total <= 0:

            return None

        # Short liquidations：
        # upward pressure / shorts squeezed
        #
        # Long liquidations：
        # downward pressure / longs flushed
        score = (
            short_liquidations
            -
            long_liquidations
        ) / total

        smaller = max(
            min(
                long_liquidations,
                short_liquidations,
            ),
            1e-9,
        )

        larger = max(
            long_liquidations,
            short_liquidations,
        )

        imbalance_ratio = (
            larger
            /
            smaller
        )

        if (
            imbalance_ratio
            >=
            self.config
            .liquidation_extreme_ratio
        ):

            crowding = 1.0

            confidence = 0.85

        elif (
            imbalance_ratio
            >=
            self.config
            .liquidation_strong_ratio
        ):

            crowding = 0.80

            confidence = 0.80

        elif (
            imbalance_ratio
            >=
            self.config
            .liquidation_soft_ratio
        ):

            crowding = 0.50

            confidence = 0.72

        else:

            crowding = 0.20

            confidence = 0.65

        return SentimentSignal(
            source=(
                SentimentSource
                .LIQUIDATION
            ),

            name=(
                "liquidation_imbalance"
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            confidence=confidence,

            crowding_score=(
                crowding
            ),

            directional_bias=(
                self._score_bias(
                    score
                )
            ),

            value={
                "long":
                    long_liquidations,

                "short":
                    short_liquidations,

                "imbalance_ratio":
                    imbalance_ratio,
            },

            description=(
                "Short liquidations dominate."
                if score > 0
                else
                "Long liquidations dominate."
                if score < 0
                else
                "Liquidations are balanced."
            ),

            metadata={
                "raw":
                    dict(
                        data
                    ),
            },
        )

    # =================================
    # Market activity
    # =================================

    def _analyze_market_activity(
        self,
        data: dict[
            str,
            Any,
        ],
    ) -> SentimentSignal | None:

        change_pct = (
            self._extract_float(
                data,
                (
                    "price_change_pct",
                    "priceChangePct",
                    "change_pct",
                    "changePct",
                    "return_pct",
                ),
            )
        )

        if change_pct is None:

            return None

        score = (
            self._signed_scale(
                change_pct,
                self.config
                .activity_extreme_pct,
            )
        )

        magnitude = abs(
            change_pct
        )

        if (
            magnitude
            >=
            self.config
            .activity_extreme_pct
        ):

            confidence = 0.82

        elif (
            magnitude
            >=
            self.config
            .activity_strong_pct
        ):

            confidence = 0.75

        elif (
            magnitude
            >=
            self.config
            .activity_soft_pct
        ):

            confidence = 0.68

        else:

            confidence = 0.60

        return SentimentSignal(
            source=(
                SentimentSource
                .MARKET_ACTIVITY
            ),

            name=(
                "price_activity"
            ),

            score=score,

            confidence=confidence,

            crowding_score=0.0,

            directional_bias=(
                self._score_bias(
                    score
                )
            ),

            value=change_pct,

            description=(
                "Recent price activity "
                "is positive."
                if change_pct > 0
                else
                "Recent price activity "
                "is negative."
                if change_pct < 0
                else
                "Recent price activity "
                "is flat."
            ),

            metadata={
                "raw":
                    dict(
                        data
                    ),
            },
        )

    # =================================
    # Aggregate metrics
    # =================================

    def _build_metrics(
        self,
        signals: list[
            SentimentSignal
        ],
    ) -> SentimentMetrics:

        if not signals:

            return (
                SentimentMetrics()
            )

        total_weight = 0.0

        weighted_score = 0.0

        weighted_crowding = 0.0

        bullish_weight = 0.0

        bearish_weight = 0.0

        neutral_weight = 0.0

        available_source_weight = 0.0

        expected_source_weights = (
            self._source_weights()
        )

        seen_sources: set[
            SentimentSource
        ] = set()

        directional_values: list[
            tuple[
                float,
                float,
            ]
        ] = []

        for signal in signals:

            source_weight = (
                expected_source_weights
                .get(
                    signal.source,
                    0.10,
                )
            )

            effective_weight = (
                source_weight
                *
                signal.confidence
            )

            if effective_weight <= 0:

                continue

            total_weight += (
                effective_weight
            )

            weighted_score += (
                signal.score
                *
                effective_weight
            )

            weighted_crowding += (
                signal.crowding_score
                *
                effective_weight
            )

            directional_values.append(
                (
                    signal.score,
                    effective_weight,
                )
            )

            if signal.score > 0.10:

                bullish_weight += (
                    effective_weight
                    *
                    abs(
                        signal.score
                    )
                )

            elif signal.score < -0.10:

                bearish_weight += (
                    effective_weight
                    *
                    abs(
                        signal.score
                    )
                )

            else:

                neutral_weight += (
                    effective_weight
                )

            if (
                signal.source
                not in seen_sources
            ):

                seen_sources.add(
                    signal.source
                )

                available_source_weight += (
                    source_weight
                )

        if total_weight <= 0:

            return SentimentMetrics(
                signal_count=len(
                    signals
                )
            )

        composite = (
            weighted_score
            /
            total_weight
        )

        crowding = (
            weighted_crowding
            /
            total_weight
        )

        direction_total = (
            bullish_weight
            +
            bearish_weight
            +
            neutral_weight
        )

        if direction_total > 0:

            bullish_score = (
                bullish_weight
                /
                direction_total
            )

            bearish_score = (
                bearish_weight
                /
                direction_total
            )

            neutral_score = (
                neutral_weight
                /
                direction_total
            )

        else:

            bullish_score = 0.0

            bearish_score = 0.0

            neutral_score = 1.0

        expected_total = sum(
            expected_source_weights
            .values()
        )

        data_quality = (
            available_source_weight
            /
            expected_total
            if expected_total > 0
            else 0.0
        )

        disagreement = (
            self._calculate_disagreement(
                directional_values,
                composite,
            )
        )

        return SentimentMetrics(
            bullish_score=(
                self._clamp01(
                    bullish_score
                )
            ),

            bearish_score=(
                self._clamp01(
                    bearish_score
                )
            ),

            neutral_score=(
                self._clamp01(
                    neutral_score
                )
            ),

            composite_score=(
                self._clamp_signed(
                    composite
                )
            ),

            crowding_score=(
                self._clamp01(
                    crowding
                )
            ),

            data_quality_score=(
                self._clamp01(
                    data_quality
                )
            ),

            disagreement_score=(
                self._clamp01(
                    disagreement
                )
            ),

            signal_count=len(
                signals
            ),
        )

    def _calculate_disagreement(
        self,
        values: list[
            tuple[
                float,
                float,
            ]
        ],
        mean: float,
    ) -> float:
        """
        Weighted mean absolute deviation。

        訊號方向越互相矛盾，
        disagreement 越高。
        """

        if len(
            values
        ) <= 1:

            return 0.0

        total_weight = sum(
            weight
            for _,
            weight
            in values
        )

        if total_weight <= 0:

            return 0.0

        deviation = sum(
            abs(
                value
                -
                mean
            )
            *
            weight

            for value,
            weight
            in values
        )

        deviation /= (
            total_weight
        )

        # 最大差距約 2，
        # normalize 到 0~1。
        return self._clamp01(
            deviation
            /
            1.25
        )

    # =================================
    # Regime
    # =================================

    def _resolve_regime(
        self,
        score: float,
    ) -> SentimentRegime:

        if (
            score
            >=
            self.config
            .extreme_bullish_threshold
        ):

            return (
                SentimentRegime
                .EXTREME_BULLISH
            )

        if (
            score
            >=
            self.config
            .bullish_threshold
        ):

            return (
                SentimentRegime.BULLISH
            )

        if (
            score
            <=
            self.config
            .extreme_bearish_threshold
        ):

            return (
                SentimentRegime
                .EXTREME_BEARISH
            )

        if (
            score
            <=
            self.config
            .bearish_threshold
        ):

            return (
                SentimentRegime.BEARISH
            )

        return (
            SentimentRegime.NEUTRAL
        )

    # =================================
    # Crowding side
    # =================================

    def _resolve_crowding_side(
        self,
        signals: list[
            SentimentSignal
        ],
    ) -> CrowdingSide:

        numerator = 0.0

        denominator = 0.0

        for signal in signals:

            if (
                signal.crowding_score
                <= 0
            ):

                continue

            weight = (
                signal.confidence
                *
                signal.crowding_score
            )

            numerator += (
                signal.score
                *
                weight
            )

            denominator += (
                weight
            )

        if denominator <= 0:

            return (
                CrowdingSide.UNKNOWN
            )

        score = (
            numerator
            /
            denominator
        )

        if (
            score
            >=
            self.config
            .crowding_side_threshold
        ):

            return (
                CrowdingSide.LONG
            )

        if (
            score
            <=
            -
            self.config
            .crowding_side_threshold
        ):

            return (
                CrowdingSide.SHORT
            )

        return (
            CrowdingSide.BALANCED
        )

    # =================================
    # Helpers
    # =================================

    def _source_weights(
        self,
    ) -> dict[
        SentimentSource,
        float,
    ]:

        return {
            SentimentSource.FUNDING:
                self.config
                .funding_weight,

            SentimentSource.OPEN_INTEREST:
                self.config
                .open_interest_weight,

            SentimentSource.LONG_SHORT_RATIO:
                self.config
                .long_short_weight,

            SentimentSource.SOCIAL:
                self.config
                .social_weight,

            SentimentSource.LIQUIDATION:
                self.config
                .liquidation_weight,

            SentimentSource.MARKET_ACTIVITY:
                self.config
                .market_activity_weight,
        }

    @staticmethod
    def _extract_float(
        data: dict[
            str,
            Any,
        ],
        keys: tuple[
            str,
            ...,
        ],
    ) -> float | None:

        for key in keys:

            if key not in data:

                continue

            value = (
                data.get(
                    key
                )
            )

            if value is None:

                continue

            try:

                number = float(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if not math.isfinite(
                number
            ):

                continue

            return number

        return None

    @staticmethod
    def _clamp01(
        value: float,
    ) -> float:

        return max(
            0.0,
            min(
                1.0,
                float(
                    value
                ),
            ),
        )

    @staticmethod
    def _clamp_signed(
        value: float,
    ) -> float:

        return max(
            -1.0,
            min(
                1.0,
                float(
                    value
                ),
            ),
        )

    @classmethod
    def _signed_scale(
        cls,
        value: float,
        extreme: float,
    ) -> float:

        if extreme <= 0:

            return 0.0

        return (
            cls._clamp_signed(
                value
                /
                extreme
            )
        )

    @classmethod
    def _magnitude_scale(
        cls,
        value: float,
        extreme: float,
    ) -> float:

        if extreme <= 0:

            return 0.0

        return (
            cls._clamp01(
                abs(
                    value
                )
                /
                extreme
            )
        )

    @staticmethod
    def _sign(
        value: float,
    ) -> float:

        if value > 0:

            return 1.0

        if value < 0:

            return -1.0

        return 0.0

    @staticmethod
    def _score_bias(
        score: float,
    ) -> TradeBias:

        if score >= 0.20:

            return (
                TradeBias.LONG
            )

        if score <= -0.20:

            return (
                TradeBias.SHORT
            )

        return (
            TradeBias.NEUTRAL
        )
