from __future__ import annotations

from ..base import (
    BaseAgent,
)

from ..models import (
    AgentName,
    AgentStatus,
    EvidenceItem,
    MarketContext,
    TradeBias,
)

from .analyzer import (
    ChartsAnalyzer,
)

from .models import (
    ChartsInput,
    ChartsOutput,
    ChartsSnapshot,
    TechnicalSignal,
    TrendRegime,
    VolatilityRegime,
)


class ChartsAgent(
    BaseAgent[
        ChartsInput,
        ChartsOutput,
    ]
):
    """
    CHARTS 技術分析 Agent。

    Responsibilities:

    - Multi-timeframe candle analysis
    - Trend analysis
    - Momentum analysis
    - Volatility analysis
    - Volume confirmation
    - Market structure
    - Support / Resistance
    - Breakout / Breakdown
    - Multi-timeframe aggregation

    注意：

    CHARTS Agent 的 bias
    代表：

        技術面方向

    並不是：

        - 下單指令
        - 最終交易決策
        - 槓桿建議
        - position sizing
        - stop loss
        - take profit

    最終交易決策交給：

        DECISION Agent

    風險限制交給：

        RISK Agent
        deterministic risk engine
    """

    name = (
        AgentName.CHARTS
    )

    def __init__(
        self,
        analyzer: (
            ChartsAnalyzer
            | None
        ) = None,
    ) -> None:

        super().__init__()

        self.analyzer = (
            analyzer
            if analyzer is not None
            else ChartsAnalyzer()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: ChartsInput,
    ) -> ChartsOutput:
        """
        執行完整 deterministic
        technical analysis。

        Pipeline:

            ChartsInput
                ↓
            ChartsAnalyzer
                ↓
            ChartsSnapshot
                ↓
            Evidence
            Summary
                ↓
            ChartsOutput
        """

        try:

            snapshot = (
                self.analyzer.analyze(
                    symbol=(
                        context.symbol
                    ),
                    payload=payload,
                )
            )

            if not (
                snapshot
                .timeframe_analyses
            ):

                return (
                    self._build_empty_output(
                        context=context,
                        snapshot=snapshot,
                    )
                )

            evidence = (
                self._build_evidence(
                    snapshot
                )
            )

            summary = (
                self._build_summary(
                    snapshot
                )
            )

            return ChartsOutput(
                agent=self.name,

                status=(
                    AgentStatus.SUCCESS
                ),

                symbol=(
                    context.symbol
                ),

                bias=(
                    snapshot.bias
                ),

                confidence=(
                    snapshot.confidence
                ),

                summary=summary,

                evidence=evidence,

                composite_score=(
                    snapshot
                    .composite_score
                ),

                trend_regime=(
                    snapshot
                    .trend_regime
                ),

                volatility_regime=(
                    snapshot
                    .volatility_regime
                ),

                primary_timeframe=(
                    snapshot
                    .primary_timeframe
                ),

                signals=(
                    snapshot.signals
                ),

                timeframe_analyses=(
                    snapshot
                    .timeframe_analyses
                ),

                market_structure=(
                    snapshot
                    .market_structure
                ),

                data_quality_score=(
                    snapshot
                    .data_quality_score
                ),

                disagreement_score=(
                    snapshot
                    .disagreement_score
                ),

                data={
                    "composite_score":
                        snapshot
                        .composite_score,

                    "trend_regime":
                        snapshot
                        .trend_regime
                        .value,

                    "volatility_regime":
                        snapshot
                        .volatility_regime
                        .value,

                    "primary_timeframe":
                        snapshot
                        .primary_timeframe,

                    "data_quality_score":
                        snapshot
                        .data_quality_score,

                    "disagreement_score":
                        snapshot
                        .disagreement_score,

                    "timeframe_count":
                        len(
                            snapshot
                            .timeframe_analyses
                        ),

                    "signal_count":
                        len(
                            snapshot
                            .signals
                        ),

                    "timeframes": [
                        timeframe
                        for timeframe
                        in (
                            snapshot
                            .timeframe_analyses
                            .keys()
                        )
                    ],

                    "timeframe_biases": {
                        timeframe:
                            analysis
                            .bias
                            .value

                        for (
                            timeframe,
                            analysis,
                        )
                        in (
                            snapshot
                            .timeframe_analyses
                            .items()
                        )
                    },

                    "timeframe_scores": {
                        timeframe:
                            analysis
                            .score

                        for (
                            timeframe,
                            analysis,
                        )
                        in (
                            snapshot
                            .timeframe_analyses
                            .items()
                        )
                    },

                    "timeframe_confidence": {
                        timeframe:
                            analysis
                            .confidence

                        for (
                            timeframe,
                            analysis,
                        )
                        in (
                            snapshot
                            .timeframe_analyses
                            .items()
                        )
                    },

                    "timeframe_trends": {
                        timeframe:
                            analysis
                            .trend_regime
                            .value

                        for (
                            timeframe,
                            analysis,
                        )
                        in (
                            snapshot
                            .timeframe_analyses
                            .items()
                        )
                    },

                    "timeframe_volatility": {
                        timeframe:
                            analysis
                            .volatility_regime
                            .value

                        for (
                            timeframe,
                            analysis,
                        )
                        in (
                            snapshot
                            .timeframe_analyses
                            .items()
                        )
                    },

                    "deterministic_analysis":
                        True,

                    "snapshot_metadata":
                        dict(
                            snapshot.metadata
                        ),
                },

                errors=[],
            )

        except Exception as exc:

            return ChartsOutput(
                agent=self.name,

                status=(
                    AgentStatus.ERROR
                ),

                symbol=(
                    context.symbol
                ),

                bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=0.0,

                summary=(
                    "Charts analysis failed."
                ),

                composite_score=0.0,

                trend_regime=(
                    TrendRegime.UNKNOWN
                ),

                volatility_regime=(
                    VolatilityRegime.UNKNOWN
                ),

                primary_timeframe=None,

                signals=[],

                timeframe_analyses={},

                market_structure={},

                data_quality_score=0.0,

                disagreement_score=0.0,

                data={
                    "deterministic_analysis":
                        False,
                },

                errors=[
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                ],
            )

    # =================================
    # Empty
    # =================================

    def _build_empty_output(
        self,
        context: MarketContext,
        snapshot: ChartsSnapshot,
    ) -> ChartsOutput:
        """
        沒有任何可用 timeframe 時：

            SKIPPED

        不視為 ERROR。
        """

        return ChartsOutput(
            agent=self.name,

            status=(
                AgentStatus.SKIPPED
            ),

            symbol=(
                context.symbol
            ),

            bias=(
                TradeBias.NEUTRAL
            ),

            confidence=0.0,

            summary=(
                "No usable chart data "
                "was available."
            ),

            composite_score=0.0,

            trend_regime=(
                snapshot
                .trend_regime
            ),

            volatility_regime=(
                snapshot
                .volatility_regime
            ),

            primary_timeframe=None,

            signals=[],

            timeframe_analyses={},

            market_structure={},

            data_quality_score=0.0,

            disagreement_score=0.0,

            data={
                "timeframe_count":
                    0,

                "signal_count":
                    0,

                "deterministic_analysis":
                    True,

                "reason":
                    snapshot
                    .metadata
                    .get(
                        "reason",
                        "no_usable_candles",
                    ),
            },

            errors=[],
        )

    # =================================
    # Evidence
    # =================================

    @staticmethod
    def _build_evidence(
        snapshot: ChartsSnapshot,
    ) -> list[
        EvidenceItem
    ]:
        """
        TechnicalSignal
            ↓
        EvidenceItem

        提供：

            DECISION
            logging
            dashboard
            database

        使用。
        """

        evidence: list[
            EvidenceItem
        ] = []

        for signal in (
            snapshot.signals
        ):

            evidence.append(
                EvidenceItem(
                    source=(
                        "charts:"
                        f"{signal.timeframe or 'unknown'}:"
                        f"{signal.signal_type.value}"
                    ),

                    description=(
                        signal.description
                        or
                        signal.name
                    ),

                    value={
                        "name":
                            signal.name,

                        "type":
                            signal
                            .signal_type
                            .value,

                        "timeframe":
                            signal
                            .timeframe,

                        "direction":
                            signal
                            .direction
                            .value,

                        "score":
                            signal.score,

                        "strength":
                            signal
                            .strength,

                        "confidence":
                            signal
                            .confidence,

                        "value":
                            signal.value,

                        "details":
                            signal.details,
                    },

                    timestamp=(
                        signal.timestamp
                    ),
                )
            )

        return evidence

    # =================================
    # Summary
    # =================================

    @classmethod
    def _build_summary(
        cls,
        snapshot: ChartsSnapshot,
    ) -> str:
        """
        建立簡潔的人類可讀
        technical summary。
        """

        bias_text = {
            TradeBias.LONG:
                "bullish",

            TradeBias.SHORT:
                "bearish",

            TradeBias.NEUTRAL:
                "neutral",

            TradeBias.WAIT:
                "wait",
        }.get(
            snapshot.bias,
            "neutral",
        )

        trend_text = {
            TrendRegime
            .STRONG_UPTREND:
                "strong uptrend",

            TrendRegime.UPTREND:
                "uptrend",

            TrendRegime.RANGE:
                "range",

            TrendRegime.DOWNTREND:
                "downtrend",

            TrendRegime
            .STRONG_DOWNTREND:
                "strong downtrend",

            TrendRegime.UNKNOWN:
                "unknown trend",
        }.get(
            snapshot
            .trend_regime,
            "unknown trend",
        )

        volatility_text = {
            VolatilityRegime.HIGH:
                "high volatility",

            VolatilityRegime.NORMAL:
                "normal volatility",

            VolatilityRegime.LOW:
                "low volatility",

            VolatilityRegime.UNKNOWN:
                "unknown volatility",
        }.get(
            snapshot
            .volatility_regime,
            "unknown volatility",
        )

        warnings: list[
            str
        ] = []

        if (
            snapshot
            .disagreement_score
            >=
            0.60
        ):

            warnings.append(
                "high timeframe disagreement"
            )

        elif (
            snapshot
            .disagreement_score
            >=
            0.40
        ):

            warnings.append(
                "mixed timeframe signals"
            )

        if (
            snapshot
            .data_quality_score
            <
            0.40
        ):

            warnings.append(
                "limited chart history"
            )

        if (
            snapshot
            .volatility_regime
            ==
            VolatilityRegime.HIGH
        ):

            warnings.append(
                "elevated volatility"
            )

        breakout_summary = (
            cls._find_breakout_summary(
                snapshot
            )
        )

        primary = (
            snapshot
            .primary_timeframe
            or
            "n/a"
        )

        summary = (
            f"Technical structure is "
            f"{bias_text} "
            f"(score "
            f"{snapshot.composite_score:+.2f})"
            f", with a "
            f"{trend_text} and "
            f"{volatility_text}. "
            f"Primary timeframe is "
            f"{primary}. "
            f"Confidence is "
            f"{snapshot.confidence:.2f}."
        )

        if breakout_summary:

            summary += (
                " "
                +
                breakout_summary
            )

        if warnings:

            summary += (
                " Caution: "
                +
                ", ".join(
                    warnings
                )
                +
                "."
            )

        return summary

    @staticmethod
    def _find_breakout_summary(
        snapshot: ChartsSnapshot,
    ) -> str:
        """
        找出最高 confidence
        breakout / breakdown signal。
        """

        breakout_signals: list[
            TechnicalSignal
        ] = [
            signal
            for signal
            in snapshot.signals
            if (
                signal.name
                ==
                "price_breakout"
            )
        ]

        if not breakout_signals:

            return ""

        strongest = max(
            breakout_signals,
            key=lambda signal:
                (
                    signal.confidence
                    *
                    signal.strength
                ),
        )

        timeframe = (
            strongest.timeframe
            or
            "unknown"
        )

        if (
            strongest.direction
            ==
            TradeBias.LONG
        ):

            return (
                f"Bullish breakout detected "
                f"on {timeframe}."
            )

        if (
            strongest.direction
            ==
            TradeBias.SHORT
        ):

            return (
                f"Bearish breakdown detected "
                f"on {timeframe}."
            )

        return ""
