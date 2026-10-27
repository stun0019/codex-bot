from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from statistics import (
    mean,
)

from typing import (
    Any,
)

from ..models import (
    TradeBias,
)

from .indicators import (
    TechnicalIndicators,
)

from .models import (
    CandleData,
    ChartsInput,
    ChartsSnapshot,
    TechnicalSignal,
    TechnicalSignalType,
    TimeframeAnalysis,
    TrendRegime,
    VolatilityRegime,
)


@dataclass(slots=True)
class ChartsAnalyzerConfig:
    """
    CHARTS deterministic analyzer 設定。

    原則：

    CHARTS 只回答：

        技術面現在偏多 / 偏空 / 中性？

    不回答：

        是否真的下單
        下多少
        用多少槓桿
        SL / TP

    最終交易決策仍交給：

        DECISION
        RISK
    """

    minimum_candles: int = 20

    use_unconfirmed_candles: bool = False

    # ---------------------------------
    # Direction thresholds
    # ---------------------------------

    bullish_threshold: float = 0.18

    strong_bullish_threshold: float = 0.55

    bearish_threshold: float = -0.18

    strong_bearish_threshold: float = -0.55

    signal_bias_threshold: float = 0.15

    # ---------------------------------
    # RSI
    # ---------------------------------

    rsi_overbought: float = 70.0

    rsi_oversold: float = 30.0

    rsi_bullish: float = 55.0

    rsi_bearish: float = 45.0

    # ---------------------------------
    # Volume
    # ---------------------------------

    volume_confirmation_ratio: float = 1.20

    volume_strong_ratio: float = 1.75

    # ---------------------------------
    # Volatility
    # ---------------------------------

    low_atr_pct: float = 0.50

    high_atr_pct: float = 2.00

    low_bandwidth_pct: float = 2.00

    high_bandwidth_pct: float = 8.00

    # ---------------------------------
    # Market structure
    # ---------------------------------

    pivot_window: int = 2

    structure_lookback: int = 80

    support_resistance_lookback: int = 100

    breakout_buffer_pct: float = 0.10

    # ---------------------------------
    # Signal weights
    # ---------------------------------

    trend_weight: float = 0.30

    momentum_weight: float = 0.20

    structure_weight: float = 0.22

    breakout_weight: float = 0.12

    volume_weight: float = 0.10

    support_resistance_weight: float = 0.06

    # ---------------------------------
    # Multi-timeframe weights
    # ---------------------------------

    timeframe_weights: dict[
        str,
        float,
    ] = field(
        default_factory=lambda: {
            "1m": 0.35,
            "3m": 0.40,
            "5m": 0.50,
            "15m": 0.70,
            "30m": 0.80,
            "1H": 1.00,
            "2H": 1.10,
            "4H": 1.30,
            "6H": 1.35,
            "12H": 1.45,
            "1D": 1.60,
            "1W": 1.80,
        }
    )

    def __post_init__(
        self,
    ) -> None:

        if self.minimum_candles <= 0:

            raise ValueError(
                "minimum_candles must "
                "be greater than 0."
            )

        if self.pivot_window <= 0:

            raise ValueError(
                "pivot_window must "
                "be greater than 0."
            )

        if (
            self.structure_lookback
            <
            self.pivot_window * 2 + 1
        ):

            raise ValueError(
                "structure_lookback "
                "is too small."
            )

        if (
            self.support_resistance_lookback
            <= 0
        ):

            raise ValueError(
                "support_resistance_lookback "
                "must be greater than 0."
            )

        if (
            self.volume_confirmation_ratio
            <= 0
        ):

            raise ValueError(
                "volume_confirmation_ratio "
                "must be greater than 0."
            )

        if (
            self.breakout_buffer_pct
            <
            0
        ):

            raise ValueError(
                "breakout_buffer_pct "
                "cannot be negative."
            )


class ChartsAnalyzer:
    """
    Deterministic multi-timeframe
    technical analyzer。

    Pipeline：

        Candles
            ↓
        Indicators
            ↓
        Trend
        Momentum
        Volume
        Volatility
        Market Structure
        Support / Resistance
        Breakout
            ↓
        Per-Timeframe Score
            ↓
        Multi-Timeframe Composite
            ↓
        ChartsSnapshot
    """

    def __init__(
        self,
        indicators: (
            TechnicalIndicators
            | None
        ) = None,
        config: (
            ChartsAnalyzerConfig
            | None
        ) = None,
    ) -> None:

        self.indicators = (
            indicators
            if indicators is not None
            else TechnicalIndicators()
        )

        self.config = (
            config
            if config is not None
            else ChartsAnalyzerConfig()
        )

    def analyze(
        self,
        symbol: str,
        payload: ChartsInput,
    ) -> ChartsSnapshot:

        timeframe_analyses: dict[
            str,
            TimeframeAnalysis,
        ] = {}

        all_signals: list[
            TechnicalSignal
        ] = []

        for (
            timeframe,
            raw_candles,
        ) in payload.candles.items():

            candles = (
                self._prepare_candles(
                    raw_candles
                )
            )

            if not candles:

                continue

            analysis = (
                self._analyze_timeframe(
                    timeframe=timeframe,
                    candles=candles,
                )
            )

            timeframe_analyses[
                timeframe
            ] = analysis

            all_signals.extend(
                analysis.signals
            )

        if not timeframe_analyses:

            return ChartsSnapshot(
                symbol=symbol,

                bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=0.0,

                composite_score=0.0,

                trend_regime=(
                    TrendRegime.UNKNOWN
                ),

                volatility_regime=(
                    VolatilityRegime.UNKNOWN
                ),

                primary_timeframe=None,

                timeframe_analyses={},

                signals=[],

                market_structure={},

                data_quality_score=0.0,

                disagreement_score=0.0,

                metadata={
                    "deterministic_analysis":
                        True,

                    "reason":
                        "no_usable_candles",
                },
            )

        (
            composite_score,
            confidence,
            data_quality,
            disagreement,
        ) = (
            self._aggregate_timeframes(
                timeframe_analyses
            )
        )

        bias = (
            self._score_bias(
                composite_score
            )
        )

        trend_regime = (
            self._resolve_trend_regime(
                composite_score
            )
        )

        volatility_regime = (
            self._aggregate_volatility(
                timeframe_analyses
            )
        )

        primary_timeframe = (
            self._resolve_primary_timeframe(
                timeframe_analyses
            )
        )

        market_structure = (
            self._build_global_structure(
                timeframe_analyses
            )
        )

        return ChartsSnapshot(
            symbol=symbol,

            bias=bias,

            confidence=confidence,

            composite_score=(
                self._clamp_signed(
                    composite_score
                )
            ),

            trend_regime=(
                trend_regime
            ),

            volatility_regime=(
                volatility_regime
            ),

            primary_timeframe=(
                primary_timeframe
            ),

            timeframe_analyses=(
                timeframe_analyses
            ),

            signals=all_signals,

            market_structure=(
                market_structure
            ),

            data_quality_score=(
                data_quality
            ),

            disagreement_score=(
                disagreement
            ),

            metadata={
                "deterministic_analysis":
                    True,

                "timeframe_count":
                    len(
                        timeframe_analyses
                    ),

                "signal_count":
                    len(
                        all_signals
                    ),

                "timeframes":
                    list(
                        timeframe_analyses
                        .keys()
                    ),
            },
        )

    # =================================
    # Timeframe analysis
    # =================================

    def _analyze_timeframe(
        self,
        timeframe: str,
        candles: list[
            CandleData
        ],
    ) -> TimeframeAnalysis:

        indicators = (
            self.indicators.calculate(
                candles
            )
        )

        signals: list[
            TechnicalSignal
        ] = []

        trend_signal = (
            self._analyze_trend(
                timeframe=timeframe,
                indicators=indicators,
            )
        )

        if trend_signal is not None:

            signals.append(
                trend_signal
            )

        rsi_signal = (
            self._analyze_rsi(
                timeframe=timeframe,
                indicators=indicators,
            )
        )

        if rsi_signal is not None:

            signals.append(
                rsi_signal
            )

        macd_signal = (
            self._analyze_macd(
                timeframe=timeframe,
                indicators=indicators,
            )
        )

        if macd_signal is not None:

            signals.append(
                macd_signal
            )

        volume_signal = (
            self._analyze_volume(
                timeframe=timeframe,
                indicators=indicators,
            )
        )

        if volume_signal is not None:

            signals.append(
                volume_signal
            )

        volatility_signal = (
            self._analyze_volatility(
                timeframe=timeframe,
                indicators=indicators,
            )
        )

        if (
            volatility_signal
            is not None
        ):

            signals.append(
                volatility_signal
            )

        structure = (
            self._analyze_structure(
                candles
            )
        )

        structure_signal = (
            self._structure_signal(
                timeframe=timeframe,
                structure=structure,
            )
        )

        if structure_signal is not None:

            signals.append(
                structure_signal
            )

        support_resistance = (
            self._support_resistance(
                candles=candles,
                structure=structure,
            )
        )

        sr_signal = (
            self._support_resistance_signal(
                timeframe=timeframe,
                candles=candles,
                levels=(
                    support_resistance
                ),
            )
        )

        if sr_signal is not None:

            signals.append(
                sr_signal
            )

        breakout_signal = (
            self._breakout_signal(
                timeframe=timeframe,
                candles=candles,
                levels=(
                    support_resistance
                ),
                indicators=indicators,
            )
        )

        if breakout_signal is not None:

            signals.append(
                breakout_signal
            )

        (
            score,
            confidence,
            disagreement,
        ) = (
            self._aggregate_signals(
                signals
            )
        )

        data_quality = (
            self._timeframe_data_quality(
                candles=candles,
                indicators=indicators,
            )
        )

        confidence *= (
            0.50
            +
            data_quality
            *
            0.50
        )

        confidence = (
            self._clamp01(
                confidence
            )
        )

        bias = (
            self._score_bias(
                score
            )
        )

        trend_regime = (
            self._resolve_trend_regime(
                score
            )
        )

        volatility_regime = (
            self._resolve_volatility_regime(
                indicators
            )
        )

        market_structure = {
            **structure,

            "support_resistance":
                support_resistance,
        }

        return TimeframeAnalysis(
            timeframe=timeframe,

            candle_count=len(
                candles
            ),

            bias=bias,

            score=(
                self._clamp_signed(
                    score
                )
            ),

            confidence=confidence,

            trend_regime=(
                trend_regime
            ),

            volatility_regime=(
                volatility_regime
            ),

            indicators=indicators,

            market_structure=(
                market_structure
            ),

            signals=signals,

            data_quality_score=(
                data_quality
            ),

            disagreement_score=(
                disagreement
            ),
        )

    # =================================
    # Trend
    # =================================

    def _analyze_trend(
        self,
        timeframe: str,
        indicators: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        ema_data = (
            indicators.get(
                "ema",
                {},
            )
        )

        close = (
            self._safe_float(
                indicators.get(
                    "latest_close"
                )
            )
        )

        ema20 = (
            self._ema_value(
                ema_data,
                20,
            )
        )

        ema50 = (
            self._ema_value(
                ema_data,
                50,
            )
        )

        ema200 = (
            self._ema_value(
                ema_data,
                200,
            )
        )

        available = [
            value
            for value
            in (
                ema20,
                ema50,
                ema200,
            )
            if value is not None
        ]

        if (
            close is None
            or not available
        ):

            return None

        components: list[
            float
        ] = []

        reasons: list[
            str
        ] = []

        if ema20 is not None:

            if close > ema20:

                components.append(
                    0.35
                )

                reasons.append(
                    "price above EMA20"
                )

            elif close < ema20:

                components.append(
                    -0.35
                )

                reasons.append(
                    "price below EMA20"
                )

        if (
            ema20 is not None
            and ema50 is not None
        ):

            if ema20 > ema50:

                components.append(
                    0.55
                )

                reasons.append(
                    "EMA20 above EMA50"
                )

            elif ema20 < ema50:

                components.append(
                    -0.55
                )

                reasons.append(
                    "EMA20 below EMA50"
                )

        if (
            ema50 is not None
            and ema200 is not None
        ):

            if ema50 > ema200:

                components.append(
                    0.70
                )

                reasons.append(
                    "EMA50 above EMA200"
                )

            elif ema50 < ema200:

                components.append(
                    -0.70
                )

                reasons.append(
                    "EMA50 below EMA200"
                )

        if (
            close is not None
            and ema200 is not None
        ):

            if close > ema200:

                components.append(
                    0.50
                )

            elif close < ema200:

                components.append(
                    -0.50
                )

        if not components:

            return None

        score = (
            mean(
                components
            )
        )

        strength = (
            min(
                1.0,
                abs(
                    score
                ),
            )
        )

        confidence = (
            len(
                available
            )
            /
            3.0
        )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType.TREND
            ),

            name=(
                "ema_trend"
            ),

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            strength=strength,

            confidence=(
                self._clamp01(
                    confidence
                )
            ),

            value={
                "close":
                    close,

                "ema20":
                    ema20,

                "ema50":
                    ema50,

                "ema200":
                    ema200,
            },

            description=(
                ", ".join(
                    reasons
                )
                if reasons
                else
                "EMA trend is neutral."
            ),
        )

    # =================================
    # RSI
    # =================================

    def _analyze_rsi(
        self,
        timeframe: str,
        indicators: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        rsi = (
            self._safe_float(
                indicators
                .get(
                    "rsi",
                    {},
                )
                .get(
                    "value"
                )
            )
        )

        if rsi is None:

            return None

        if (
            rsi
            >=
            self.config
            .rsi_overbought
        ):

            score = 0.45

            description = (
                "RSI is overbought; "
                "momentum is bullish but "
                "extended."
            )

            strength = (
                self._clamp01(
                    (
                        rsi
                        -
                        50.0
                    )
                    /
                    50.0
                )
            )

        elif (
            rsi
            <=
            self.config
            .rsi_oversold
        ):

            score = -0.45

            description = (
                "RSI is oversold; "
                "momentum is bearish but "
                "extended."
            )

            strength = (
                self._clamp01(
                    (
                        50.0
                        -
                        rsi
                    )
                    /
                    50.0
                )
            )

        elif (
            rsi
            >=
            self.config
            .rsi_bullish
        ):

            score = (
                (
                    rsi
                    -
                    50.0
                )
                /
                30.0
            )

            description = (
                "RSI shows bullish "
                "momentum."
            )

            strength = (
                abs(
                    score
                )
            )

        elif (
            rsi
            <=
            self.config
            .rsi_bearish
        ):

            score = -(
                (
                    50.0
                    -
                    rsi
                )
                /
                30.0
            )

            description = (
                "RSI shows bearish "
                "momentum."
            )

            strength = (
                abs(
                    score
                )
            )

        else:

            score = 0.0

            strength = 0.20

            description = (
                "RSI is neutral."
            )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType
                .MOMENTUM
            ),

            name="rsi",

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            strength=(
                self._clamp01(
                    strength
                )
            ),

            confidence=0.85,

            value=rsi,

            description=description,
        )

    # =================================
    # MACD
    # =================================

    def _analyze_macd(
        self,
        timeframe: str,
        indicators: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        macd = (
            indicators.get(
                "macd",
                {},
            )
        )

        line = (
            self._safe_float(
                macd.get(
                    "value"
                )
            )
        )

        signal_line = (
            self._safe_float(
                macd.get(
                    "signal"
                )
            )
        )

        histogram = (
            self._safe_float(
                macd.get(
                    "histogram"
                )
            )
        )

        if (
            line is None
            or signal_line is None
            or histogram is None
        ):

            return None

        if histogram > 0:

            score = 0.60

            if line > 0:

                score += 0.15

            description = (
                "MACD histogram is "
                "positive."
            )

        elif histogram < 0:

            score = -0.60

            if line < 0:

                score -= 0.15

            description = (
                "MACD histogram is "
                "negative."
            )

        else:

            score = 0.0

            description = (
                "MACD is neutral."
            )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType
                .MOMENTUM
            ),

            name="macd",

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            strength=(
                min(
                    1.0,
                    0.55
                    +
                    abs(score)
                    *
                    0.45,
                )
            ),

            confidence=0.85,

            value={
                "macd":
                    line,

                "signal":
                    signal_line,

                "histogram":
                    histogram,
            },

            description=description,
        )

    # =================================
    # Volume
    # =================================

    def _analyze_volume(
        self,
        timeframe: str,
        indicators: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        volume = (
            indicators.get(
                "volume",
                {},
            )
        )

        ratio = (
            self._safe_float(
                volume.get(
                    "ratio"
                )
            )
        )

        price_change = (
            self._safe_float(
                indicators.get(
                    "price_change_pct"
                )
            )
        )

        if (
            ratio is None
            or price_change is None
        ):

            return None

        if (
            ratio
            <
            self.config
            .volume_confirmation_ratio
        ):

            score = (
                self._sign(
                    price_change
                )
                *
                0.15
            )

            strength = (
                self._clamp01(
                    ratio
                    /
                    self.config
                    .volume_confirmation_ratio
                )
            )

            description = (
                "Price move has limited "
                "volume confirmation."
            )

        else:

            volume_strength = (
                self._clamp01(
                    (
                        ratio
                        -
                        1.0
                    )
                    /
                    max(
                        0.01,
                        (
                            self.config
                            .volume_strong_ratio
                            -
                            1.0
                        ),
                    )
                )
            )

            score = (
                self._sign(
                    price_change
                )
                *
                (
                    0.40
                    +
                    0.50
                    *
                    volume_strength
                )
            )

            strength = (
                0.50
                +
                0.50
                *
                volume_strength
            )

            description = (
                "Price move is confirmed "
                "by elevated volume."
            )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType.VOLUME
            ),

            name="volume_confirmation",

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            strength=(
                self._clamp01(
                    strength
                )
            ),

            confidence=0.75,

            value={
                "volume_ratio":
                    ratio,

                "price_change_pct":
                    price_change,
            },

            description=description,
        )

    # =================================
    # Volatility
    # =================================

    def _analyze_volatility(
        self,
        timeframe: str,
        indicators: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        atr_pct = (
            self._safe_float(
                indicators
                .get(
                    "atr",
                    {},
                )
                .get(
                    "percent"
                )
            )
        )

        bandwidth = (
            self._safe_float(
                indicators
                .get(
                    "bollinger",
                    {},
                )
                .get(
                    "bandwidth_pct"
                )
            )
        )

        if (
            atr_pct is None
            and bandwidth is None
        ):

            return None

        regime = (
            self._resolve_volatility_regime(
                indicators
            )
        )

        strength = 0.50

        if (
            regime
            ==
            VolatilityRegime.HIGH
        ):

            strength = 0.90

            description = (
                "Volatility is elevated."
            )

        elif (
            regime
            ==
            VolatilityRegime.LOW
        ):

            strength = 0.70

            description = (
                "Volatility is compressed."
            )

        else:

            description = (
                "Volatility is normal."
            )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType
                .VOLATILITY
            ),

            name="volatility_regime",

            timeframe=timeframe,

            direction=(
                TradeBias.NEUTRAL
            ),

            score=0.0,

            strength=strength,

            confidence=0.80,

            value={
                "regime":
                    regime.value,

                "atr_pct":
                    atr_pct,

                "bollinger_bandwidth_pct":
                    bandwidth,
            },

            description=description,
        )

    # =================================
    # Market structure
    # =================================

    def _analyze_structure(
        self,
        candles: list[
            CandleData
        ],
    ) -> dict[
        str,
        Any,
    ]:

        subset = (
            candles[
                -
                self.config
                .structure_lookback:
            ]
        )

        highs = (
            self._find_pivot_highs(
                subset
            )
        )

        lows = (
            self._find_pivot_lows(
                subset
            )
        )

        structure = "unknown"

        score = 0.0

        higher_high = None
        higher_low = None

        if len(highs) >= 2:

            higher_high = (
                highs[-1][1]
                >
                highs[-2][1]
            )

        if len(lows) >= 2:

            higher_low = (
                lows[-1][1]
                >
                lows[-2][1]
            )

        if (
            higher_high is True
            and higher_low is True
        ):

            structure = (
                "higher_high_higher_low"
            )

            score = 0.85

        elif (
            higher_high is False
            and higher_low is False
        ):

            structure = (
                "lower_high_lower_low"
            )

            score = -0.85

        elif (
            higher_high is True
            and higher_low is False
        ):

            structure = (
                "expanding_range"
            )

            score = 0.10

        elif (
            higher_high is False
            and higher_low is True
        ):

            structure = (
                "compression"
            )

            score = 0.0

        return {
            "type":
                structure,

            "score":
                score,

            "higher_high":
                higher_high,

            "higher_low":
                higher_low,

            "pivot_highs": [
                {
                    "index":
                        index,

                    "price":
                        price,
                }
                for index,
                price
                in highs[-5:]
            ],

            "pivot_lows": [
                {
                    "index":
                        index,

                    "price":
                        price,
                }
                for index,
                price
                in lows[-5:]
            ],
        }

    def _structure_signal(
        self,
        timeframe: str,
        structure: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        score = (
            self._safe_float(
                structure.get(
                    "score"
                )
            )
        )

        if score is None:

            return None

        structure_type = str(
            structure.get(
                "type",
                "unknown",
            )
        )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType
                .STRUCTURE
            ),

            name="market_structure",

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            strength=(
                max(
                    0.30,
                    abs(
                        score
                    ),
                )
            ),

            confidence=(
                0.85
                if abs(score) >= 0.50
                else 0.60
            ),

            value=structure_type,

            description=(
                f"Market structure: "
                f"{structure_type}."
            ),

            details=structure,
        )

    # =================================
    # Support / Resistance
    # =================================

    def _support_resistance(
        self,
        candles: list[
            CandleData
        ],
        structure: dict[
            str,
            Any,
        ],
    ) -> dict[
        str,
        Any,
    ]:

        recent = (
            candles[
                -
                self.config
                .support_resistance_lookback:
            ]
        )

        if not recent:

            return {}

        current_close = (
            recent[-1]
            .close
        )

        pivot_highs = (
            structure.get(
                "pivot_highs",
                [],
            )
        )

        pivot_lows = (
            structure.get(
                "pivot_lows",
                [],
            )
        )

        resistance_candidates = [
            float(
                item["price"]
            )
            for item
            in pivot_highs
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "price"
                )
                is not None
                and float(
                    item["price"]
                )
                >=
                current_close
            )
        ]

        support_candidates = [
            float(
                item["price"]
            )
            for item
            in pivot_lows
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "price"
                )
                is not None
                and float(
                    item["price"]
                )
                <=
                current_close
            )
        ]

        resistance = (
            min(
                resistance_candidates
            )
            if resistance_candidates
            else max(
                candle.high
                for candle
                in recent[:-1]
            )
            if len(recent) > 1
            else None
        )

        support = (
            max(
                support_candidates
            )
            if support_candidates
            else min(
                candle.low
                for candle
                in recent[:-1]
            )
            if len(recent) > 1
            else None
        )

        distance_to_resistance = (
            self._distance_pct(
                current_close,
                resistance,
            )
            if resistance is not None
            else None
        )

        distance_to_support = (
            self._distance_pct(
                current_close,
                support,
            )
            if support is not None
            else None
        )

        return {
            "current_price":
                current_close,

            "support":
                support,

            "resistance":
                resistance,

            "distance_to_support_pct":
                distance_to_support,

            "distance_to_resistance_pct":
                distance_to_resistance,
        }

    def _support_resistance_signal(
        self,
        timeframe: str,
        candles: list[
            CandleData
        ],
        levels: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        if not candles:

            return None

        close = (
            candles[-1]
            .close
        )

        support = (
            self._safe_float(
                levels.get(
                    "support"
                )
            )
        )

        resistance = (
            self._safe_float(
                levels.get(
                    "resistance"
                )
            )
        )

        if (
            support is None
            and resistance is None
        ):

            return None

        score = 0.0

        description = (
            "Price is between support "
            "and resistance."
        )

        nearest_distance = None

        if (
            support is not None
            and support > 0
        ):

            support_distance = abs(
                (
                    close
                    -
                    support
                )
                /
                support
                *
                100.0
            )

            if (
                nearest_distance is None
                or support_distance
                <
                nearest_distance
            ):

                nearest_distance = (
                    support_distance
                )

            if (
                close >= support
                and support_distance
                <= 1.0
            ):

                score += 0.25

                description = (
                    "Price is near support."
                )

        if (
            resistance is not None
            and resistance > 0
        ):

            resistance_distance = abs(
                (
                    resistance
                    -
                    close
                )
                /
                resistance
                *
                100.0
            )

            if (
                nearest_distance is None
                or resistance_distance
                <
                nearest_distance
            ):

                nearest_distance = (
                    resistance_distance
                )

            if (
                close <= resistance
                and resistance_distance
                <= 1.0
            ):

                score -= 0.25

                description = (
                    "Price is near resistance."
                )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType
                .SUPPORT_RESISTANCE
            ),

            name="support_resistance",

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=(
                self._clamp_signed(
                    score
                )
            ),

            strength=(
                0.50
                if nearest_distance
                is not None
                else 0.30
            ),

            confidence=0.65,

            value={
                "close":
                    close,

                "support":
                    support,

                "resistance":
                    resistance,

                "nearest_distance_pct":
                    nearest_distance,
            },

            description=description,
        )

    # =================================
    # Breakout
    # =================================

    def _breakout_signal(
        self,
        timeframe: str,
        candles: list[
            CandleData
        ],
        levels: dict[
            str,
            Any,
        ],
        indicators: dict[
            str,
            Any,
        ],
    ) -> TechnicalSignal | None:

        if len(candles) < 2:

            return None

        close = (
            candles[-1]
            .close
        )

        previous_close = (
            candles[-2]
            .close
        )

        resistance = (
            self._safe_float(
                levels.get(
                    "resistance"
                )
            )
        )

        support = (
            self._safe_float(
                levels.get(
                    "support"
                )
            )
        )

        volume_ratio = (
            self._safe_float(
                indicators
                .get(
                    "volume",
                    {},
                )
                .get(
                    "ratio"
                )
            )
        )

        buffer = (
            self.config
            .breakout_buffer_pct
            /
            100.0
        )

        score = 0.0

        breakout_type = None

        if (
            resistance is not None
            and resistance > 0
        ):

            breakout_level = (
                resistance
                *
                (
                    1.0
                    +
                    buffer
                )
            )

            if (
                close
                >
                breakout_level
                and previous_close
                <=
                breakout_level
            ):

                score = 0.75

                breakout_type = (
                    "bullish_breakout"
                )

        if (
            support is not None
            and support > 0
        ):

            breakdown_level = (
                support
                *
                (
                    1.0
                    -
                    buffer
                )
            )

            if (
                close
                <
                breakdown_level
                and previous_close
                >=
                breakdown_level
            ):

                score = -0.75

                breakout_type = (
                    "bearish_breakdown"
                )

        if breakout_type is None:

            return None

        volume_confirmed = (
            volume_ratio is not None
            and
            volume_ratio
            >=
            self.config
            .volume_confirmation_ratio
        )

        if volume_confirmed:

            score *= 1.20

            confidence = 0.90

            strength = 0.95

        else:

            confidence = 0.65

            strength = 0.70

        score = (
            self._clamp_signed(
                score
            )
        )

        return TechnicalSignal(
            signal_type=(
                TechnicalSignalType
                .BREAKOUT
            ),

            name="price_breakout",

            timeframe=timeframe,

            direction=(
                self._signal_bias(
                    score
                )
            ),

            score=score,

            strength=strength,

            confidence=confidence,

            value={
                "type":
                    breakout_type,

                "close":
                    close,

                "support":
                    support,

                "resistance":
                    resistance,

                "volume_ratio":
                    volume_ratio,

                "volume_confirmed":
                    volume_confirmed,
            },

            description=(
                (
                    "Bullish breakout "
                    "detected."
                )
                if score > 0
                else
                "Bearish breakdown "
                "detected."
            ),
        )

    # =================================
    # Pivot detection
    # =================================

    def _find_pivot_highs(
        self,
        candles: list[
            CandleData
        ],
    ) -> list[
        tuple[
            int,
            float,
        ]
    ]:

        window = (
            self.config
            .pivot_window
        )

        result: list[
            tuple[
                int,
                float,
            ]
        ] = []

        if (
            len(candles)
            <
            window * 2 + 1
        ):

            return result

        for index in range(
            window,
            len(candles) - window,
        ):

            value = (
                candles[index]
                .high
            )

            left = [
                candles[i].high
                for i
                in range(
                    index - window,
                    index,
                )
            ]

            right = [
                candles[i].high
                for i
                in range(
                    index + 1,
                    index + window + 1,
                )
            ]

            if (
                value
                >
                max(left)
                and value
                >=
                max(right)
            ):

                result.append(
                    (
                        index,
                        float(
                            value
                        ),
                    )
                )

        return result

    def _find_pivot_lows(
        self,
        candles: list[
            CandleData
        ],
    ) -> list[
        tuple[
            int,
            float,
        ]
    ]:

        window = (
            self.config
            .pivot_window
        )

        result: list[
            tuple[
                int,
                float,
            ]
        ] = []

        if (
            len(candles)
            <
            window * 2 + 1
        ):

            return result

        for index in range(
            window,
            len(candles) - window,
        ):

            value = (
                candles[index]
                .low
            )

            left = [
                candles[i].low
                for i
                in range(
                    index - window,
                    index,
                )
            ]

            right = [
                candles[i].low
                for i
                in range(
                    index + 1,
                    index + window + 1,
                )
            ]

            if (
                value
                <
                min(left)
                and value
                <=
                min(right)
            ):

                result.append(
                    (
                        index,
                        float(
                            value
                        ),
                    )
                )

        return result

    # =================================
    # Signal aggregation
    # =================================

    def _aggregate_signals(
        self,
        signals: list[
            TechnicalSignal
        ],
    ) -> tuple[
        float,
        float,
        float,
    ]:

        directional = [
            signal
            for signal
            in signals
            if (
                signal.signal_type
                !=
                TechnicalSignalType
                .VOLATILITY
            )
        ]

        if not directional:

            return (
                0.0,
                0.0,
                0.0,
            )

        numerator = 0.0
        denominator = 0.0

        weighted_values: list[
            tuple[
                float,
                float,
            ]
        ] = []

        confidence_values: list[
            float
        ] = []

        for signal in directional:

            type_weight = (
                self._signal_type_weight(
                    signal.signal_type
                )
            )

            weight = (
                type_weight
                *
                max(
                    0.10,
                    signal.strength,
                )
                *
                signal.confidence
            )

            if weight <= 0:

                continue

            numerator += (
                signal.score
                *
                weight
            )

            denominator += (
                weight
            )

            weighted_values.append(
                (
                    signal.score,
                    weight,
                )
            )

            confidence_values.append(
                signal.confidence
            )

        if denominator <= 0:

            return (
                0.0,
                0.0,
                0.0,
            )

        score = (
            numerator
            /
            denominator
        )

        disagreement = (
            self._calculate_disagreement(
                weighted_values,
                score,
            )
        )

        average_confidence = (
            mean(
                confidence_values
            )
            if confidence_values
            else 0.0
        )

        confidence = (
            average_confidence
            *
            (
                1.0
                -
                disagreement
                *
                0.60
            )
        )

        return (
            self._clamp_signed(
                score
            ),

            self._clamp01(
                confidence
            ),

            self._clamp01(
                disagreement
            ),
        )

    # =================================
    # Multi-timeframe aggregation
    # =================================

    def _aggregate_timeframes(
        self,
        analyses: dict[
            str,
            TimeframeAnalysis,
        ],
    ) -> tuple[
        float,
        float,
        float,
        float,
    ]:

        numerator = 0.0
        denominator = 0.0

        directional_values: list[
            tuple[
                float,
                float,
            ]
        ] = []

        confidence_sum = 0.0
        quality_sum = 0.0
        raw_weight_sum = 0.0

        for (
            timeframe,
            analysis,
        ) in analyses.items():

            timeframe_weight = (
                self._timeframe_weight(
                    timeframe
                )
            )

            weight = (
                timeframe_weight
                *
                max(
                    0.10,
                    analysis
                    .data_quality_score,
                )
                *
                max(
                    0.10,
                    analysis
                    .confidence,
                )
            )

            numerator += (
                analysis.score
                *
                weight
            )

            denominator += (
                weight
            )

            directional_values.append(
                (
                    analysis.score,
                    weight,
                )
            )

            confidence_sum += (
                analysis.confidence
                *
                timeframe_weight
            )

            quality_sum += (
                analysis
                .data_quality_score
                *
                timeframe_weight
            )

            raw_weight_sum += (
                timeframe_weight
            )

        if denominator <= 0:

            return (
                0.0,
                0.0,
                0.0,
                0.0,
            )

        composite = (
            numerator
            /
            denominator
        )

        disagreement = (
            self._calculate_disagreement(
                directional_values,
                composite,
            )
        )

        avg_confidence = (
            confidence_sum
            /
            raw_weight_sum
            if raw_weight_sum > 0
            else 0.0
        )

        data_quality = (
            quality_sum
            /
            raw_weight_sum
            if raw_weight_sum > 0
            else 0.0
        )

        confidence = (
            avg_confidence
            *
            (
                1.0
                -
                disagreement
                *
                0.65
            )
            *
            (
                0.50
                +
                0.50
                *
                data_quality
            )
        )

        return (
            self._clamp_signed(
                composite
            ),

            self._clamp01(
                confidence
            ),

            self._clamp01(
                data_quality
            ),

            self._clamp01(
                disagreement
            ),
        )

    # =================================
    # Global structure
    # =================================

    def _build_global_structure(
        self,
        analyses: dict[
            str,
            TimeframeAnalysis,
        ],
    ) -> dict[
        str,
        Any,
    ]:

        result: dict[
            str,
            Any,
        ] = {}

        for (
            timeframe,
            analysis,
        ) in analyses.items():

            result[
                timeframe
            ] = {
                "trend_regime":
                    analysis
                    .trend_regime
                    .value,

                "bias":
                    analysis
                    .bias
                    .value,

                "score":
                    analysis.score,

                "structure":
                    analysis
                    .market_structure,
            }

        return result

    # =================================
    # Regimes
    # =================================

    def _resolve_trend_regime(
        self,
        score: float,
    ) -> TrendRegime:

        if (
            score
            >=
            self.config
            .strong_bullish_threshold
        ):

            return (
                TrendRegime
                .STRONG_UPTREND
            )

        if (
            score
            >=
            self.config
            .bullish_threshold
        ):

            return (
                TrendRegime.UPTREND
            )

        if (
            score
            <=
            self.config
            .strong_bearish_threshold
        ):

            return (
                TrendRegime
                .STRONG_DOWNTREND
            )

        if (
            score
            <=
            self.config
            .bearish_threshold
        ):

            return (
                TrendRegime.DOWNTREND
            )

        return (
            TrendRegime.RANGE
        )

    def _resolve_volatility_regime(
        self,
        indicators: dict[
            str,
            Any,
        ],
    ) -> VolatilityRegime:

        atr_pct = (
            self._safe_float(
                indicators
                .get(
                    "atr",
                    {},
                )
                .get(
                    "percent"
                )
            )
        )

        bandwidth = (
            self._safe_float(
                indicators
                .get(
                    "bollinger",
                    {},
                )
                .get(
                    "bandwidth_pct"
                )
            )
        )

        high_votes = 0
        low_votes = 0
        available = 0

        if atr_pct is not None:

            available += 1

            if (
                atr_pct
                >=
                self.config
                .high_atr_pct
            ):

                high_votes += 1

            elif (
                atr_pct
                <=
                self.config
                .low_atr_pct
            ):

                low_votes += 1

        if bandwidth is not None:

            available += 1

            if (
                bandwidth
                >=
                self.config
                .high_bandwidth_pct
            ):

                high_votes += 1

            elif (
                bandwidth
                <=
                self.config
                .low_bandwidth_pct
            ):

                low_votes += 1

        if available == 0:

            return (
                VolatilityRegime.UNKNOWN
            )

        if high_votes > low_votes:

            return (
                VolatilityRegime.HIGH
            )

        if low_votes > high_votes:

            return (
                VolatilityRegime.LOW
            )

        return (
            VolatilityRegime.NORMAL
        )

    def _aggregate_volatility(
        self,
        analyses: dict[
            str,
            TimeframeAnalysis,
        ],
    ) -> VolatilityRegime:

        scores = {
            VolatilityRegime.LOW:
                -1.0,

            VolatilityRegime.NORMAL:
                0.0,

            VolatilityRegime.HIGH:
                1.0,
        }

        numerator = 0.0
        denominator = 0.0

        for (
            timeframe,
            analysis,
        ) in analyses.items():

            if (
                analysis
                .volatility_regime
                ==
                VolatilityRegime.UNKNOWN
            ):

                continue

            weight = (
                self._timeframe_weight(
                    timeframe
                )
            )

            numerator += (
                scores[
                    analysis
                    .volatility_regime
                ]
                *
                weight
            )

            denominator += (
                weight
            )

        if denominator <= 0:

            return (
                VolatilityRegime.UNKNOWN
            )

        score = (
            numerator
            /
            denominator
        )

        if score >= 0.35:

            return (
                VolatilityRegime.HIGH
            )

        if score <= -0.35:

            return (
                VolatilityRegime.LOW
            )

        return (
            VolatilityRegime.NORMAL
        )

    # =================================
    # Data quality
    # =================================

    def _timeframe_data_quality(
        self,
        candles: list[
            CandleData
        ],
        indicators: dict[
            str,
            Any,
        ],
    ) -> float:

        indicator_quality = (
            self._safe_float(
                indicators.get(
                    "data_quality"
                )
            )
        )

        if indicator_quality is None:

            indicator_quality = 0.0

        minimum_quality = (
            self._clamp01(
                len(candles)
                /
                self.config
                .minimum_candles
            )
        )

        confirmed_count = sum(
            1
            for candle
            in candles
            if candle.confirmed
        )

        confirmation_quality = (
            confirmed_count
            /
            len(candles)
            if candles
            else 0.0
        )

        return (
            self._clamp01(
                indicator_quality
                *
                0.60
                +
                minimum_quality
                *
                0.25
                +
                confirmation_quality
                *
                0.15
            )
        )

    # =================================
    # Helpers
    # =================================

    def _prepare_candles(
        self,
        candles: list[
            CandleData
        ],
    ) -> list[
        CandleData
    ]:

        result = sorted(
            candles,
            key=lambda candle:
                candle.timestamp,
        )

        if not (
            self.config
            .use_unconfirmed_candles
        ):

            result = [
                candle
                for candle
                in result
                if candle.confirmed
            ]

        return result

    def _resolve_primary_timeframe(
        self,
        analyses: dict[
            str,
            TimeframeAnalysis,
        ],
    ) -> str | None:

        if not analyses:

            return None

        return max(
            analyses.keys(),
            key=lambda timeframe:
                (
                    self._timeframe_weight(
                        timeframe
                    )
                    *
                    analyses[
                        timeframe
                    ]
                    .data_quality_score
                ),
        )

    def _signal_type_weight(
        self,
        signal_type: (
            TechnicalSignalType
        ),
    ) -> float:

        mapping = {
            TechnicalSignalType.TREND:
                self.config
                .trend_weight,

            TechnicalSignalType.MOMENTUM:
                self.config
                .momentum_weight,

            TechnicalSignalType.STRUCTURE:
                self.config
                .structure_weight,

            TechnicalSignalType.BREAKOUT:
                self.config
                .breakout_weight,

            TechnicalSignalType.VOLUME:
                self.config
                .volume_weight,

            TechnicalSignalType
            .SUPPORT_RESISTANCE:
                self.config
                .support_resistance_weight,

            TechnicalSignalType.OTHER:
                0.05,
        }

        return mapping.get(
            signal_type,
            0.0,
        )

    def _timeframe_weight(
        self,
        timeframe: str,
    ) -> float:

        if (
            timeframe
            in self.config
            .timeframe_weights
        ):

            return (
                self.config
                .timeframe_weights[
                    timeframe
                ]
            )

        normalized = (
            timeframe.strip()
        )

        if (
            normalized
            in self.config
            .timeframe_weights
        ):

            return (
                self.config
                .timeframe_weights[
                    normalized
                ]
            )

        return 1.0

    def _calculate_disagreement(
        self,
        values: list[
            tuple[
                float,
                float,
            ]
        ],
        mean_value: float,
    ) -> float:

        if len(values) <= 1:

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
                mean_value
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

        return (
            self._clamp01(
                deviation
                /
                1.25
            )
        )

    def _score_bias(
        self,
        score: float,
    ) -> TradeBias:

        if (
            score
            >=
            self.config
            .bullish_threshold
        ):

            return (
                TradeBias.LONG
            )

        if (
            score
            <=
            self.config
            .bearish_threshold
        ):

            return (
                TradeBias.SHORT
            )

        return (
            TradeBias.NEUTRAL
        )

    def _signal_bias(
        self,
        score: float,
    ) -> TradeBias:

        if (
            score
            >=
            self.config
            .signal_bias_threshold
        ):

            return (
                TradeBias.LONG
            )

        if (
            score
            <=
            -
            self.config
            .signal_bias_threshold
        ):

            return (
                TradeBias.SHORT
            )

        return (
            TradeBias.NEUTRAL
        )

    @staticmethod
    def _ema_value(
        ema_data: dict[
            str,
            Any,
        ],
        period: int,
    ) -> float | None:

        item = (
            ema_data.get(
                str(
                    period
                )
            )
        )

        if not isinstance(
            item,
            dict,
        ):

            return None

        return (
            ChartsAnalyzer
            ._safe_float(
                item.get(
                    "value"
                )
            )
        )

    @staticmethod
    def _distance_pct(
        price: float,
        level: float,
    ) -> float | None:

        if level == 0:

            return None

        return (
            (
                price
                -
                level
            )
            /
            level
            *
            100.0
        )

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float | None:

        if value is None:

            return None

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if (
            number != number
        ):

            return None

        if number in (
            float("inf"),
            float("-inf"),
        ):

            return None

        return number

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
