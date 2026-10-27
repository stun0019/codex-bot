from __future__ import annotations

from ..base import BaseAgent

from ..models import (
    AgentName,
    AgentStatus,
    EvidenceItem,
    MarketContext,
    TradeBias,
)

from .analyzer import (
    SentimentAnalyzer,
)

from .models import (
    CrowdingSide,
    SentimentInput,
    SentimentOutput,
    SentimentRegime,
    SentimentSnapshot,
)


class SentimentAgent(
    BaseAgent[
        SentimentInput,
        SentimentOutput,
    ]
):
    """
    市場情緒分析 Agent。

    Responsibilities:

    - Funding positioning
    - Open Interest behavior
    - Long / Short Ratio
    - Social sentiment
    - Liquidation imbalance
    - Market activity
    - Crowding detection
    - Sentiment regime
    - Signal disagreement
    - Data quality assessment

    注意：

    SENTIMENT Agent 的 bias
    代表市場情緒方向，

    並不是：

        - 直接交易指令
        - 進場訊號
        - 槓桿建議
        - position sizing
        - stop loss
        - take profit

    最終交易決策由：

        DECISION Agent

    負責。
    """

    name = (
        AgentName.SENTIMENT
    )

    def __init__(
        self,
        analyzer: (
            SentimentAnalyzer
            | None
        ) = None,
    ) -> None:

        super().__init__()

        self.analyzer = (
            analyzer
            if analyzer is not None
            else SentimentAnalyzer()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: SentimentInput,
    ) -> SentimentOutput:
        """
        執行完整 deterministic
        sentiment analysis。

        Pipeline:

            SentimentInput
                ↓
            SentimentAnalyzer
                ↓
            SentimentSnapshot
                ↓
            Bias
            Confidence
            Evidence
                ↓
            SentimentOutput
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

            if not snapshot.signals:

                return (
                    self._build_empty_output(
                        context=context,
                        snapshot=snapshot,
                    )
                )

            bias = (
                self._resolve_bias(
                    snapshot
                )
            )

            confidence = (
                self._calculate_confidence(
                    snapshot
                )
            )

            evidence = (
                self._build_evidence(
                    snapshot
                )
            )

            summary = (
                self._build_summary(
                    snapshot=snapshot,
                    bias=bias,
                    confidence=(
                        confidence
                    ),
                )
            )

            return SentimentOutput(
                agent=self.name,

                status=(
                    AgentStatus.SUCCESS
                ),

                symbol=context.symbol,

                bias=bias,

                confidence=(
                    confidence
                ),

                summary=summary,

                evidence=evidence,

                regime=(
                    snapshot.regime
                ),

                crowding_side=(
                    snapshot
                    .crowding_side
                ),

                metrics=(
                    snapshot.metrics
                ),

                signals=(
                    snapshot.signals
                ),

                data={
                    "regime":
                        snapshot
                        .regime
                        .value,

                    "crowding_side":
                        snapshot
                        .crowding_side
                        .value,

                    "composite_score":
                        snapshot
                        .metrics
                        .composite_score,

                    "bullish_score":
                        snapshot
                        .metrics
                        .bullish_score,

                    "bearish_score":
                        snapshot
                        .metrics
                        .bearish_score,

                    "neutral_score":
                        snapshot
                        .metrics
                        .neutral_score,

                    "crowding_score":
                        snapshot
                        .metrics
                        .crowding_score,

                    "data_quality_score":
                        snapshot
                        .metrics
                        .data_quality_score,

                    "disagreement_score":
                        snapshot
                        .metrics
                        .disagreement_score,

                    "signal_count":
                        snapshot
                        .metrics
                        .signal_count,

                    "extreme_crowding":
                        (
                            snapshot
                            .metrics
                            .crowding_score
                            >=
                            0.80
                        ),

                    "high_disagreement":
                        (
                            snapshot
                            .metrics
                            .disagreement_score
                            >=
                            0.60
                        ),

                    "deterministic_analysis":
                        True,

                    "snapshot_metadata":
                        dict(
                            snapshot.metadata
                        ),
                },
            )

        except Exception as exc:

            return SentimentOutput(
                agent=self.name,

                status=(
                    AgentStatus.ERROR
                ),

                symbol=context.symbol,

                bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=0.0,

                summary=(
                    "Sentiment analysis "
                    "failed."
                ),

                errors=[
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                ],

                data={
                    "deterministic_analysis":
                        False,
                },
            )

    def _build_empty_output(
        self,
        context: MarketContext,
        snapshot: SentimentSnapshot,
    ) -> SentimentOutput:
        """
        沒有任何有效 sentiment
        signal 時：

            SKIPPED

        而不是 ERROR。
        """

        return SentimentOutput(
            agent=self.name,

            status=(
                AgentStatus.SKIPPED
            ),

            symbol=context.symbol,

            bias=(
                TradeBias.NEUTRAL
            ),

            confidence=0.0,

            summary=(
                "No usable sentiment "
                "signals were available."
            ),

            regime=(
                snapshot.regime
            ),

            crowding_side=(
                snapshot
                .crowding_side
            ),

            metrics=(
                snapshot.metrics
            ),

            signals=[],

            data={
                "regime":
                    snapshot
                    .regime
                    .value,

                "crowding_side":
                    snapshot
                    .crowding_side
                    .value,

                "signal_count":
                    0,

                "deterministic_analysis":
                    True,
            },
        )

    @staticmethod
    def _resolve_bias(
        snapshot: SentimentSnapshot,
    ) -> TradeBias:
        """
        SENTIMENT bias 代表：

            市場情緒 / positioning
            的主要方向。

        不會因為 crowding
        自動反轉方向。

        例如：

            EXTREME_BULLISH
            + LONG crowded

        仍然輸出：

            bias = LONG

        但：

            crowding_score 很高

        DECISION Agent 之後可判斷：

            不適合追多。
        """

        regime = (
            snapshot.regime
        )

        if regime in (
            SentimentRegime.BULLISH,
            SentimentRegime
            .EXTREME_BULLISH,
        ):

            return (
                TradeBias.LONG
            )

        if regime in (
            SentimentRegime.BEARISH,
            SentimentRegime
            .EXTREME_BEARISH,
        ):

            return (
                TradeBias.SHORT
            )

        return (
            TradeBias.NEUTRAL
        )

    @staticmethod
    def _calculate_confidence(
        snapshot: SentimentSnapshot,
    ) -> float:
        """
        Confidence 綜合：

        1. composite strength
        2. data quality
        3. signal agreement

        crowding 不直接降低
        sentiment 判斷可信度。

        因為：

        「市場非常 bullish
        而且非常 crowded」

        本身仍可能是高可信度
        sentiment observation。

        Crowding 會另外傳給
        DECISION / RISK。
        """

        metrics = (
            snapshot.metrics
        )

        strength = abs(
            metrics.composite_score
        )

        quality = (
            metrics
            .data_quality_score
        )

        agreement = (
            1.0
            -
            metrics
            .disagreement_score
        )

        # 即使 composite 接近 0，
        # 如果資料完整且訊號一致，
        # 仍可以高可信度判斷：
        #
        # "市場目前中性"
        if (
            snapshot.regime
            ==
            SentimentRegime.NEUTRAL
        ):

            directional_factor = (
                0.55
                +
                (
                    1.0
                    -
                    min(
                        1.0,
                        strength,
                    )
                )
                *
                0.20
            )

        else:

            directional_factor = (
                0.45
                +
                strength
                *
                0.55
            )

        confidence = (
            quality
            *
            agreement
            *
            directional_factor
        )

        # Signal 數太少時降低 confidence。
        signal_count = (
            metrics.signal_count
        )

        if signal_count == 1:

            confidence *= 0.65

        elif signal_count == 2:

            confidence *= 0.80

        elif signal_count == 3:

            confidence *= 0.90

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

    @staticmethod
    def _build_evidence(
        snapshot: SentimentSnapshot,
    ) -> list[
        EvidenceItem
    ]:
        """
        每個 normalized signal
        都轉成 EvidenceItem。

        讓：

        - DECISION
        - logs
        - dashboard
        - database

        可以知道 SENTIMENT
        是依據哪些訊號做判斷。
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
                        f"sentiment:"
                        f"{signal.source.value}"
                    ),

                    description=(
                        signal.description
                        or
                        signal.name
                    ),

                    value={
                        "name":
                            signal.name,

                        "score":
                            signal.score,

                        "confidence":
                            signal
                            .confidence,

                        "crowding_score":
                            signal
                            .crowding_score,

                        "bias":
                            signal
                            .directional_bias
                            .value,

                        "value":
                            signal.value,
                    },

                    timestamp=(
                        signal.timestamp
                    ),
                )
            )

        return evidence

    @staticmethod
    def _build_summary(
        snapshot: SentimentSnapshot,
        bias: TradeBias,
        confidence: float,
    ) -> str:
        """
        建立簡短的人類可讀 summary。
        """

        metrics = (
            snapshot.metrics
        )

        regime_text = {
            SentimentRegime
            .EXTREME_BULLISH:
                "extremely bullish",

            SentimentRegime.BULLISH:
                "bullish",

            SentimentRegime.NEUTRAL:
                "neutral",

            SentimentRegime.BEARISH:
                "bearish",

            SentimentRegime
            .EXTREME_BEARISH:
                "extremely bearish",
        }.get(
            snapshot.regime,
            "neutral",
        )

        crowding_text = {
            CrowdingSide.LONG:
                "long-side crowding",

            CrowdingSide.SHORT:
                "short-side crowding",

            CrowdingSide.BALANCED:
                "balanced positioning",

            CrowdingSide.UNKNOWN:
                "unknown crowding",
        }.get(
            snapshot.crowding_side,
            "unknown crowding",
        )

        warnings: list[
            str
        ] = []

        if (
            metrics.crowding_score
            >=
            0.80
        ):

            warnings.append(
                "extreme crowding"
            )

        elif (
            metrics.crowding_score
            >=
            0.60
        ):

            warnings.append(
                "elevated crowding"
            )

        if (
            metrics
            .disagreement_score
            >=
            0.60
        ):

            warnings.append(
                "high signal disagreement"
            )

        if (
            metrics
            .data_quality_score
            <
            0.40
        ):

            warnings.append(
                "limited data coverage"
            )

        summary = (
            f"Sentiment is "
            f"{regime_text} "
            f"(score "
            f"{metrics.composite_score:+.2f})"
            f", with "
            f"{crowding_text} "
            f"(crowding "
            f"{metrics.crowding_score:.2f}). "
            f"Bias is "
            f"{bias.value.upper()} "
            f"with confidence "
            f"{confidence:.2f}."
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
