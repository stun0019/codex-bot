from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from ..models import (
    TradeBias,
)

from .models import (
    DecisionGate,
    DecisionGateStatus,
    DecisionInput,
    DecisionMetrics,
    DecisionSnapshot,
)


@dataclass(slots=True)
class DecisionAnalyzerConfig:
    charts_weight: float = 0.55

    sentiment_weight: float = 0.25

    news_weight: float = 0.20

    minimum_directional_score: float = 0.20

    minimum_action_confidence: float = 0.55

    minimum_data_quality: float = 0.45

    maximum_disagreement: float = 0.65

    strong_opposing_news_score: float = 0.55

    extreme_crowding_score: float = 0.85

    minimum_scout_opportunity_score: float = 0.20

    anchor_timeframes: tuple[
        str,
        str,
    ] = (
        "4H",
        "1H",
    )

    entry_timeframe: str = "15m"

    charts_components: dict[
        str,
        float,
    ] = field(
        default_factory=lambda: {
            "overall":
                0.45,

            "4H":
                0.30,

            "1H":
                0.20,

            "15m":
                0.05,
        }
    )


class DecisionAnalyzer:
    """
    Final deterministic decision layer.

    DECISION 的責任：

        1. 整合方向證據
        2. 檢查多週期一致性
        3. 檢查新聞反向風險
        4. 檢查 crowding
        5. 使用 RISK 作為 final gate
        6. 輸出 LONG / SHORT / WAIT

    DECISION 不負責：

        - 下單
        - 修改止損
        - 交易所 API
        - 繞過 hard risk engine
    """

    def __init__(
        self,
        config: (
            DecisionAnalyzerConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else DecisionAnalyzerConfig()
        )

    def analyze(
        self,
        symbol: str,
        payload: DecisionInput,
    ) -> DecisionSnapshot:

        symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        self._validate_symbols(
            symbol=symbol,
            payload=payload,
        )

        charts_score = (
            self._charts_score(
                payload.charts_result
            )
        )

        sentiment_score = (
            self._sentiment_score(
                payload.sentiment_result
            )
        )

        news_score = (
            self._news_score(
                symbol=symbol,
                result=(
                    payload.news_result
                ),
            )
        )

        scout_score = (
            self._scout_score(
                symbol=symbol,
                result=(
                    payload.scout_result
                ),
            )
        )

        directional_score = (
            self._directional_score(
                charts_score=charts_score,
                sentiment_score=(
                    sentiment_score
                ),
                news_score=news_score,
            )
        )

        directional_bias = (
            self._score_to_bias(
                directional_score
            )
        )

        bullish_score, bearish_score = (
            self._directional_components(
                charts_score=charts_score,
                sentiment_score=(
                    sentiment_score
                ),
                news_score=news_score,
            )
        )

        disagreement_score = (
            self._disagreement_score(
                charts_score=charts_score,
                sentiment_score=(
                    sentiment_score
                ),
                news_score=news_score,
                charts_result=(
                    payload.charts_result
                ),
                sentiment_result=(
                    payload.sentiment_result
                ),
            )
        )

        data_quality_score = (
            self._data_quality_score(
                charts_result=(
                    payload.charts_result
                ),
                sentiment_result=(
                    payload.sentiment_result
                ),
                news_result=(
                    payload.news_result
                ),
            )
        )

        confidence = (
            self._decision_confidence(
                directional_score=(
                    directional_score
                ),
                disagreement_score=(
                    disagreement_score
                ),
                data_quality_score=(
                    data_quality_score
                ),
            )
        )

        crowding = (
            self._crowding_state(
                result=(
                    payload.sentiment_result
                ),
                directional_bias=(
                    directional_bias
                ),
            )
        )

        if crowding[
            "same_side_extreme"
        ]:

            confidence *= 0.82

        if (
            scout_score
            is not None
        ):

            confidence *= (
                0.90
                +
                0.10
                *
                scout_score
            )

        confidence = (
            self._clamp01(
                confidence
            )
        )

        gates: list[
            DecisionGate
        ] = []

        # =================================
        # CHARTS availability
        # =================================

        if charts_score is None:

            gates.append(
                DecisionGate(
                    name="charts_available",

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "CHARTS result is required "
                        "for final direction."
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="charts_available",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "CHARTS data is available."
                    ),

                    value=charts_score,
                )
            )

        # =================================
        # Direction strength
        # =================================

        if (
            directional_bias
            in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
        ):

            gates.append(
                DecisionGate(
                    name="directional_strength",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "Directional score exceeds "
                        "minimum threshold."
                    ),

                    value={
                        "bias":
                            directional_bias.value,

                        "score":
                            directional_score,
                    },
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="directional_strength",

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "Directional evidence is "
                        "too weak or neutral."
                    ),

                    value=(
                        directional_score
                    ),
                )
            )

        # =================================
        # 4H / 1H anchor
        # =================================

        gates.append(
            self._anchor_timeframe_gate(
                result=(
                    payload.charts_result
                ),
                directional_bias=(
                    directional_bias
                ),
            )
        )

        # =================================
        # Entry timeframe
        # =================================

        gates.append(
            self._entry_timeframe_gate(
                result=(
                    payload.charts_result
                ),
                directional_bias=(
                    directional_bias
                ),
            )
        )

        # =================================
        # Data quality
        # =================================

        if (
            data_quality_score
            >=
            self.config
            .minimum_data_quality
        ):

            gates.append(
                DecisionGate(
                    name="data_quality",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "Data quality is sufficient."
                    ),

                    value=(
                        data_quality_score
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="data_quality",

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "Data quality is below "
                        "minimum threshold."
                    ),

                    value=(
                        data_quality_score
                    ),
                )
            )

        # =================================
        # Disagreement
        # =================================

        if (
            disagreement_score
            <=
            self.config
            .maximum_disagreement
        ):

            gates.append(
                DecisionGate(
                    name="agent_disagreement",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "Agent disagreement is "
                        "within allowed range."
                    ),

                    value=(
                        disagreement_score
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="agent_disagreement",

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "Directional agents are "
                        "too contradictory."
                    ),

                    value=(
                        disagreement_score
                    ),
                )
            )

        # =================================
        # NEWS opposition
        # =================================

        gates.append(
            self._news_gate(
                news_score=news_score,
                directional_bias=(
                    directional_bias
                ),
            )
        )

        # =================================
        # Crowding
        # =================================

        if crowding[
            "same_side_extreme"
        ]:

            gates.append(
                DecisionGate(
                    name="sentiment_crowding",

                    status=(
                        DecisionGateStatus.WARN
                    ),

                    blocking=False,

                    reason=(
                        "Proposed direction is on "
                        "the same side as extreme "
                        "market crowding."
                    ),

                    value=crowding,
                )
            )

        elif crowding[
            "score"
        ] is not None:

            gates.append(
                DecisionGate(
                    name="sentiment_crowding",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "No extreme same-side "
                        "crowding detected."
                    ),

                    value=crowding,
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="sentiment_crowding",

                    status=(
                        DecisionGateStatus
                        .NOT_AVAILABLE
                    ),

                    reason=(
                        "Crowding data unavailable."
                    ),
                )
            )

        # =================================
        # Confidence
        # =================================

        if (
            confidence
            >=
            self.config
            .minimum_action_confidence
        ):

            gates.append(
                DecisionGate(
                    name="decision_confidence",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "Decision confidence meets "
                        "minimum threshold."
                    ),

                    value=confidence,
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="decision_confidence",

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "Decision confidence is "
                        "below minimum threshold."
                    ),

                    value=confidence,
                )
            )

        # =================================
        # Proposed trade direction
        # =================================

        gates.append(
            self._trade_direction_gate(
                proposed_trade=(
                    payload.proposed_trade
                ),
                directional_bias=(
                    directional_bias
                ),
                require_risk_approval=(
                    payload
                    .require_risk_approval
                ),
            )
        )

        # =================================
        # RISK gate
        # =================================

        risk_gate, risk_approved = (
            self._risk_gate(
                result=(
                    payload.risk_result
                ),
                required=(
                    payload
                    .require_risk_approval
                ),
            )
        )

        gates.append(
            risk_gate
        )

        # =================================
        # SCOUT quality
        # =================================

        gates.append(
            self._scout_gate(
                scout_score
            )
        )

        blocking_failures = [
            gate
            for gate
            in gates
            if (
                gate.blocking
                and
                gate.status
                ==
                DecisionGateStatus.FAIL
            )
        ]

        if (
            directional_bias
            in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
            and
            not blocking_failures
        ):

            action = (
                directional_bias
            )

        else:

            action = (
                TradeBias.WAIT
            )

        metrics = DecisionMetrics(
            directional_score=(
                directional_score
            ),

            bullish_score=(
                bullish_score
            ),

            bearish_score=(
                bearish_score
            ),

            consensus_score=(
                self._clamp01(
                    1.0
                    -
                    disagreement_score
                )
            ),

            disagreement_score=(
                disagreement_score
            ),

            data_quality_score=(
                data_quality_score
            ),

            charts_score=(
                charts_score
            ),

            sentiment_score=(
                sentiment_score
            ),

            news_score=(
                news_score
            ),

            scout_opportunity_score=(
                scout_score
            ),
        )

        reasoning = (
            self._build_reasoning(
                action=action,
                directional_bias=(
                    directional_bias
                ),
                metrics=metrics,
                gates=gates,
                payload=payload,
            )
        )

        return DecisionSnapshot(
            symbol=symbol,

            action=action,

            directional_bias=(
                directional_bias
            ),

            confidence=confidence,

            risk_approved=(
                risk_approved
            ),

            metrics=metrics,

            gates=gates,

            reasoning=reasoning,

            metadata={
                "strategy":
                    "multi_agent_consensus_v1",

                "risk_required":
                    payload
                    .require_risk_approval,

                "blocking_failure_count":
                    len(
                        blocking_failures
                    ),

                "available_sources": {
                    "scout":
                        self._available(
                            payload.scout_result
                        ),

                    "news":
                        self._available(
                            payload.news_result
                        ),

                    "sentiment":
                        self._available(
                            payload.sentiment_result
                        ),

                    "charts":
                        self._available(
                            payload.charts_result
                        ),

                    "risk":
                        self._available(
                            payload.risk_result
                        ),
                },
            },
        )

    # =================================
    # Scores
    # =================================

    def _charts_score(
        self,
        result: dict[
            str,
            Any,
        ],
    ) -> (
        float
        | None
    ):

        if not self._available(
            result
        ):

            return None

        components: list[
            tuple[
                float,
                float,
            ]
        ] = []

        overall = (
            self._safe_float(
                result.get(
                    "composite_score"
                )
            )
        )

        if overall is None:

            overall = (
                self._bias_score(
                    result
                )
            )

        if overall is not None:

            components.append(
                (
                    self._clamp_signed(
                        overall
                    ),
                    self.config
                    .charts_components
                    .get(
                        "overall",
                        0.45,
                    ),
                )
            )

        analyses = (
            result.get(
                "timeframe_analyses",
                {}
            )
            or {}
        )

        for (
            timeframe,
            weight,
        ) in (
            self.config
            .charts_components
            .items()
        ):

            if timeframe == "overall":

                continue

            analysis = (
                analyses.get(
                    timeframe
                )
            )

            if not isinstance(
                analysis,
                dict,
            ):

                continue

            score = (
                self._safe_float(
                    analysis.get(
                        "score"
                    )
                )
            )

            if score is None:

                score = (
                    self._bias_score(
                        analysis
                    )
                )

            if score is None:

                continue

            components.append(
                (
                    self._clamp_signed(
                        score
                    ),
                    weight,
                )
            )

        if not components:

            return None

        total_weight = sum(
            weight
            for _, weight
            in components
        )

        if total_weight <= 0:

            return None

        return (
            self._clamp_signed(
                sum(
                    score
                    *
                    weight

                    for score, weight
                    in components
                )
                /
                total_weight
            )
        )

    def _sentiment_score(
        self,
        result: dict[
            str,
            Any,
        ],
    ) -> (
        float
        | None
    ):

        if not self._available(
            result
        ):

            return None

        metrics = (
            result.get(
                "metrics",
                {}
            )
            or {}
        )

        score = (
            self._safe_float(
                metrics.get(
                    "composite_score"
                )
            )
        )

        if score is not None:

            return (
                self._clamp_signed(
                    score
                )
            )

        return (
            self._bias_score(
                result
            )
        )

    def _news_score(
        self,
        symbol: str,
        result: dict[
            str,
            Any,
        ],
    ) -> (
        float
        | None
    ):

        if not self._available(
            result
        ):

            return None

        base_score = (
            self._bias_score(
                result
            )
        )

        events = (
            result.get(
                "events",
                []
            )
            or []
        )

        event_scores: list[
            float
        ] = []

        base_asset = (
            symbol
            .split(
                "-"
            )[0]
        )

        for event in events:

            if not isinstance(
                event,
                dict,
            ):

                continue

            affected = [
                str(
                    item
                )
                .strip()
                .upper()

                for item
                in (
                    event.get(
                        "affected_symbols",
                        []
                    )
                    or []
                )
            ]

            if affected:

                relevant = any(
                    (
                        item == symbol
                        or
                        item == base_asset
                        or
                        item.startswith(
                            base_asset
                            +
                            "-"
                        )
                    )

                    for item
                    in affected
                )

                if not relevant:

                    continue

            bias = (
                self._to_bias(
                    event.get(
                        "bias"
                    )
                )
            )

            sign = (
                self._bias_sign(
                    bias
                )
            )

            if sign == 0:

                continue

            impact = (
                self._safe_float(
                    event.get(
                        "impact_score"
                    )
                )
                or 0.0
            )

            confidence = (
                self._safe_float(
                    event.get(
                        "confidence"
                    )
                )
                or 0.0
            )

            event_scores.append(
                sign
                *
                self._clamp01(
                    impact
                )
                *
                self._clamp01(
                    confidence
                )
            )

        event_score = None

        if event_scores:

            event_score = (
                sum(
                    event_scores
                )
                /
                len(
                    event_scores
                )
            )

        if (
            base_score is not None
            and
            event_score is not None
        ):

            return (
                self._clamp_signed(
                    base_score
                    *
                    0.35
                    +
                    event_score
                    *
                    0.65
                )
            )

        if event_score is not None:

            return (
                self._clamp_signed(
                    event_score
                )
            )

        if base_score is not None:

            return (
                self._clamp_signed(
                    base_score
                )
            )

        return 0.0

    def _scout_score(
        self,
        symbol: str,
        result: dict[
            str,
            Any,
        ],
    ) -> (
        float
        | None
    ):

        if not self._available(
            result
        ):

            return None

        candidates = (
            result.get(
                "candidates",
                []
            )
            or []
        )

        for candidate in candidates:

            if not isinstance(
                candidate,
                dict,
            ):

                continue

            candidate_symbol = (
                str(
                    candidate.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if (
                candidate_symbol
                !=
                symbol
            ):

                continue

            score = (
                self._safe_float(
                    candidate.get(
                        "score"
                    )
                )
            )

            if score is None:

                return None

            return (
                self._clamp01(
                    score
                )
            )

        return None

    def _directional_score(
        self,
        charts_score: (
            float
            | None
        ),
        sentiment_score: (
            float
            | None
        ),
        news_score: (
            float
            | None
        ),
    ) -> float:

        components = [
            (
                charts_score,
                self.config
                .charts_weight,
            ),

            (
                sentiment_score,
                self.config
                .sentiment_weight,
            ),

            (
                news_score,
                self.config
                .news_weight,
            ),
        ]

        available = [
            (
                score,
                weight,
            )

            for score, weight
            in components

            if score is not None
        ]

        if not available:

            return 0.0

        total_weight = sum(
            weight
            for _, weight
            in available
        )

        if total_weight <= 0:

            return 0.0

        return (
            self._clamp_signed(
                sum(
                    score
                    *
                    weight

                    for score, weight
                    in available
                )
                /
                total_weight
            )
        )

    def _directional_components(
        self,
        charts_score: (
            float
            | None
        ),
        sentiment_score: (
            float
            | None
        ),
        news_score: (
            float
            | None
        ),
    ) -> tuple[
        float,
        float,
    ]:

        components = [
            (
                charts_score,
                self.config
                .charts_weight,
            ),

            (
                sentiment_score,
                self.config
                .sentiment_weight,
            ),

            (
                news_score,
                self.config
                .news_weight,
            ),
        ]

        available = [
            (
                score,
                weight,
            )

            for score, weight
            in components

            if score is not None
        ]

        if not available:

            return (
                0.0,
                0.0,
            )

        total_weight = sum(
            weight
            for _, weight
            in available
        )

        bullish = sum(
            max(
                score,
                0.0,
            )
            *
            weight

            for score, weight
            in available
        )

        bearish = sum(
            max(
                -score,
                0.0,
            )
            *
            weight

            for score, weight
            in available
        )

        return (
            self._clamp01(
                bullish
                /
                total_weight
            ),

            self._clamp01(
                bearish
                /
                total_weight
            ),
        )

    # =================================
    # Quality / disagreement
    # =================================

    def _data_quality_score(
        self,
        charts_result: dict[
            str,
            Any,
        ],
        sentiment_result: dict[
            str,
            Any,
        ],
        news_result: dict[
            str,
            Any,
        ],
    ) -> float:

        values: list[
            tuple[
                float,
                float,
            ]
        ] = []

        if self._available(
            charts_result
        ):

            charts_quality = (
                self._safe_float(
                    charts_result.get(
                        "data_quality_score"
                    )
                )
            )

            if charts_quality is None:

                charts_quality = (
                    self._safe_float(
                        charts_result.get(
                            "confidence"
                        )
                    )
                    or 0.0
                )

            values.append(
                (
                    self._clamp01(
                        charts_quality
                    ),
                    self.config
                    .charts_weight,
                )
            )

        if self._available(
            sentiment_result
        ):

            metrics = (
                sentiment_result.get(
                    "metrics",
                    {}
                )
                or {}
            )

            sentiment_quality = (
                self._safe_float(
                    metrics.get(
                        "data_quality_score"
                    )
                )
            )

            if sentiment_quality is None:

                sentiment_quality = (
                    self._safe_float(
                        sentiment_result.get(
                            "confidence"
                        )
                    )
                    or 0.0
                )

            values.append(
                (
                    self._clamp01(
                        sentiment_quality
                    ),
                    self.config
                    .sentiment_weight,
                )
            )

        if self._available(
            news_result
        ):

            news_quality = (
                self._safe_float(
                    news_result.get(
                        "confidence"
                    )
                )
                or 0.0
            )

            source_articles = (
                self._safe_float(
                    (
                        news_result.get(
                            "data",
                            {}
                        )
                        or {}
                    ).get(
                        "source_articles"
                    )
                )
                or 0.0
            )

            if (
                source_articles > 0
            ):

                news_quality = max(
                    news_quality,
                    0.55,
                )

            values.append(
                (
                    self._clamp01(
                        news_quality
                    ),
                    self.config
                    .news_weight,
                )
            )

        if not values:

            return 0.0

        total_weight = sum(
            weight
            for _, weight
            in values
        )

        return (
            self._clamp01(
                sum(
                    value
                    *
                    weight

                    for value, weight
                    in values
                )
                /
                total_weight
            )
        )

    def _disagreement_score(
        self,
        charts_score: (
            float
            | None
        ),
        sentiment_score: (
            float
            | None
        ),
        news_score: (
            float
            | None
        ),
        charts_result: dict[
            str,
            Any,
        ],
        sentiment_result: dict[
            str,
            Any,
        ],
    ) -> float:

        components = [
            (
                charts_score,
                self.config
                .charts_weight,
            ),

            (
                sentiment_score,
                self.config
                .sentiment_weight,
            ),

            (
                news_score,
                self.config
                .news_weight,
            ),
        ]

        positive = 0.0
        negative = 0.0

        for score, weight in components:

            if score is None:

                continue

            if score > 0:

                positive += (
                    score
                    *
                    weight
                )

            elif score < 0:

                negative += (
                    abs(
                        score
                    )
                    *
                    weight
                )

        total_directional = (
            positive
            +
            negative
        )

        if total_directional > 0:

            cross_source = (
                2.0
                *
                min(
                    positive,
                    negative,
                )
                /
                total_directional
            )

        else:

            cross_source = 0.0

        charts_internal = (
            self._safe_float(
                charts_result.get(
                    "disagreement_score"
                )
            )
            or 0.0
        )

        sentiment_metrics = (
            sentiment_result.get(
                "metrics",
                {}
            )
            or {}
        )

        sentiment_internal = (
            self._safe_float(
                sentiment_metrics.get(
                    "disagreement_score"
                )
            )
            or 0.0
        )

        return (
            self._clamp01(
                cross_source
                *
                0.70
                +
                self._clamp01(
                    charts_internal
                )
                *
                0.20
                +
                self._clamp01(
                    sentiment_internal
                )
                *
                0.10
            )
        )

    def _decision_confidence(
        self,
        directional_score: float,
        disagreement_score: float,
        data_quality_score: float,
    ) -> float:

        direction_strength = abs(
            directional_score
        )

        consensus = (
            1.0
            -
            disagreement_score
        )

        raw = (
            direction_strength
            *
            0.72
            +
            consensus
            *
            0.28
        )

        quality_modifier = (
            0.55
            +
            0.45
            *
            data_quality_score
        )

        return (
            self._clamp01(
                raw
                *
                quality_modifier
            )
        )

    # =================================
    # Gates
    # =================================

    def _anchor_timeframe_gate(
        self,
        result: dict[
            str,
            Any,
        ],
        directional_bias: TradeBias,
    ) -> DecisionGate:

        if not self._available(
            result
        ):

            return DecisionGate(
                name="higher_timeframe_alignment",

                status=(
                    DecisionGateStatus
                    .NOT_AVAILABLE
                ),

                blocking=False,

                reason=(
                    "CHARTS result unavailable."
                ),
            )

        analyses = (
            result.get(
                "timeframe_analyses",
                {}
            )
            or {}
        )

        first_tf, second_tf = (
            self.config
            .anchor_timeframes
        )

        first_bias = (
            self._timeframe_bias(
                analyses.get(
                    first_tf
                )
            )
        )

        second_bias = (
            self._timeframe_bias(
                analyses.get(
                    second_tf
                )
            )
        )

        directional = (
            TradeBias.LONG,
            TradeBias.SHORT,
        )

        if (
            first_bias in directional
            and
            second_bias in directional
        ):

            if (
                first_bias
                !=
                second_bias
            ):

                return DecisionGate(
                    name=(
                        "higher_timeframe_alignment"
                    ),

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        f"{first_tf} and "
                        f"{second_tf} point in "
                        "opposite directions."
                    ),

                    value={
                        first_tf:
                            first_bias.value,

                        second_tf:
                            second_bias.value,
                    },
                )

            if (
                directional_bias
                in directional
                and
                first_bias
                !=
                directional_bias
            ):

                return DecisionGate(
                    name=(
                        "higher_timeframe_alignment"
                    ),

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "Composite direction conflicts "
                        "with higher-timeframe trend."
                    ),

                    value={
                        first_tf:
                            first_bias.value,

                        second_tf:
                            second_bias.value,

                        "composite":
                            directional_bias.value,
                    },
                )

            return DecisionGate(
                name="higher_timeframe_alignment",

                status=(
                    DecisionGateStatus.PASS
                ),

                reason=(
                    f"{first_tf} and "
                    f"{second_tf} are aligned."
                ),

                value={
                    first_tf:
                        first_bias.value,

                    second_tf:
                        second_bias.value,
                },
            )

        return DecisionGate(
            name="higher_timeframe_alignment",

            status=(
                DecisionGateStatus.WARN
            ),

            blocking=False,

            reason=(
                "Higher-timeframe alignment "
                "is only partially available."
            ),

            value={
                first_tf:
                    first_bias.value,

                second_tf:
                    second_bias.value,
            },
        )

    def _entry_timeframe_gate(
        self,
        result: dict[
            str,
            Any,
        ],
        directional_bias: TradeBias,
    ) -> DecisionGate:

        timeframe = (
            self.config
            .entry_timeframe
        )

        analyses = (
            result.get(
                "timeframe_analyses",
                {}
            )
            or {}
        )

        entry_bias = (
            self._timeframe_bias(
                analyses.get(
                    timeframe
                )
            )
        )

        directional = (
            TradeBias.LONG,
            TradeBias.SHORT,
        )

        if (
            directional_bias
            not in directional
        ):

            return DecisionGate(
                name="entry_timing",

                status=(
                    DecisionGateStatus
                    .NOT_AVAILABLE
                ),

                reason=(
                    "No directional bias "
                    "to evaluate entry timing."
                ),
            )

        if (
            entry_bias
            not in directional
        ):

            return DecisionGate(
                name="entry_timing",

                status=(
                    DecisionGateStatus.WARN
                ),

                blocking=False,

                reason=(
                    f"{timeframe} is neutral "
                    "or unavailable."
                ),

                value=(
                    entry_bias.value
                ),
            )

        if (
            entry_bias
            !=
            directional_bias
        ):

            return DecisionGate(
                name="entry_timing",

                status=(
                    DecisionGateStatus.FAIL
                ),

                blocking=True,

                reason=(
                    f"{timeframe} currently "
                    "moves against the main "
                    "direction. Wait for "
                    "entry confirmation."
                ),

                value={
                    "main_direction":
                        directional_bias.value,

                    timeframe:
                        entry_bias.value,
                },
            )

        return DecisionGate(
            name="entry_timing",

            status=(
                DecisionGateStatus.PASS
            ),

            reason=(
                f"{timeframe} confirms the "
                "main direction."
            ),

            value=(
                entry_bias.value
            ),
        )

    def _news_gate(
        self,
        news_score: (
            float
            | None
        ),
        directional_bias: TradeBias,
    ) -> DecisionGate:

        if news_score is None:

            return DecisionGate(
                name="news_opposition",

                status=(
                    DecisionGateStatus
                    .NOT_AVAILABLE
                ),

                reason=(
                    "NEWS data unavailable."
                ),
            )

        if (
            directional_bias
            not in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
        ):

            return DecisionGate(
                name="news_opposition",

                status=(
                    DecisionGateStatus.WARN
                ),

                reason=(
                    "No final directional bias "
                    "for NEWS comparison."
                ),

                value=news_score,
            )

        direction_sign = (
            self._bias_sign(
                directional_bias
            )
        )

        opposing = (
            news_score
            *
            direction_sign
            <
            0
        )

        if (
            opposing
            and
            abs(
                news_score
            )
            >=
            self.config
            .strong_opposing_news_score
        ):

            return DecisionGate(
                name="news_opposition",

                status=(
                    DecisionGateStatus.FAIL
                ),

                blocking=True,

                reason=(
                    "Strong NEWS evidence "
                    "opposes the proposed "
                    "market direction."
                ),

                value=news_score,
            )

        return DecisionGate(
            name="news_opposition",

            status=(
                DecisionGateStatus.PASS
            ),

            reason=(
                "No strong opposite NEWS "
                "risk detected."
            ),

            value=news_score,
        )

    def _risk_gate(
        self,
        result: dict[
            str,
            Any,
        ],
        required: bool,
    ) -> tuple[
        DecisionGate,
        bool,
    ]:

        if not required:

            return (
                DecisionGate(
                    name="risk_approval",

                    status=(
                        DecisionGateStatus.WARN
                    ),

                    blocking=False,

                    reason=(
                        "RISK approval requirement "
                        "is disabled."
                    ),
                ),
                False,
            )

        if not self._available(
            result
        ):

            return (
                DecisionGate(
                    name="risk_approval",

                    status=(
                        DecisionGateStatus.FAIL
                    ),

                    blocking=True,

                    reason=(
                        "RISK approval is required "
                        "but unavailable."
                    ),
                ),
                False,
            )

        verdict = (
            str(
                result.get(
                    "verdict",
                    "",
                )
            )
            .strip()
            .lower()
        )

        approved = bool(
            result.get(
                "approved",
                False,
            )
        )

        if (
            approved
            and
            verdict
            ==
            "approve"
        ):

            return (
                DecisionGate(
                    name="risk_approval",

                    status=(
                        DecisionGateStatus.PASS
                    ),

                    reason=(
                        "RISK approved the "
                        "proposed trade."
                    ),

                    value=verdict,
                ),
                True,
            )

        return (
            DecisionGate(
                name="risk_approval",

                status=(
                    DecisionGateStatus.FAIL
                ),

                blocking=True,

                reason=(
                    "RISK did not approve "
                    "the proposed trade."
                ),

                value=verdict
                or
                "unknown",
            ),
            False,
        )

    def _trade_direction_gate(
        self,
        proposed_trade,
        directional_bias: TradeBias,
        require_risk_approval: bool,
    ) -> DecisionGate:

        if proposed_trade is None:

            return DecisionGate(
                name="trade_direction_match",

                status=(
                    DecisionGateStatus.FAIL
                    if require_risk_approval
                    else DecisionGateStatus.WARN
                ),

                blocking=(
                    require_risk_approval
                ),

                reason=(
                    "No proposed trade is "
                    "available to bind the "
                    "direction to RISK approval."
                ),
            )

        if (
            directional_bias
            not in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
        ):

            return DecisionGate(
                name="trade_direction_match",

                status=(
                    DecisionGateStatus.FAIL
                ),

                blocking=True,

                reason=(
                    "Market direction is not "
                    "strong enough to validate "
                    "the proposed trade."
                ),
            )

        if (
            proposed_trade.side
            !=
            directional_bias
        ):

            return DecisionGate(
                name="trade_direction_match",

                status=(
                    DecisionGateStatus.FAIL
                ),

                blocking=True,

                reason=(
                    "Proposed trade direction "
                    "does not match DECISION "
                    "directional bias."
                ),

                value={
                    "proposed":
                        proposed_trade
                        .side
                        .value,

                    "decision":
                        directional_bias
                        .value,
                },
            )

        return DecisionGate(
            name="trade_direction_match",

            status=(
                DecisionGateStatus.PASS
            ),

            reason=(
                "Proposed trade direction "
                "matches DECISION bias."
            ),

            value=(
                directional_bias.value
            ),
        )

    def _scout_gate(
        self,
        score: (
            float
            | None
        ),
    ) -> DecisionGate:

        if score is None:

            return DecisionGate(
                name="scout_opportunity",

                status=(
                    DecisionGateStatus
                    .NOT_AVAILABLE
                ),

                blocking=False,

                reason=(
                    "Symbol is not present "
                    "in current SCOUT candidates."
                ),
            )

        if (
            score
            <
            self.config
            .minimum_scout_opportunity_score
        ):

            return DecisionGate(
                name="scout_opportunity",

                status=(
                    DecisionGateStatus.WARN
                ),

                blocking=False,

                reason=(
                    "SCOUT opportunity score "
                    "is relatively low."
                ),

                value=score,
            )

        return DecisionGate(
            name="scout_opportunity",

            status=(
                DecisionGateStatus.PASS
            ),

            reason=(
                "SCOUT opportunity score "
                "is acceptable."
            ),

            value=score,
        )

    # =================================
    # Sentiment crowding
    # =================================

    def _crowding_state(
        self,
        result: dict[
            str,
            Any,
        ],
        directional_bias: TradeBias,
    ) -> dict[
        str,
        Any,
    ]:

        metrics = (
            result.get(
                "metrics",
                {}
            )
            or {}
        )

        score = (
            self._safe_float(
                metrics.get(
                    "crowding_score"
                )
            )
        )

        side = (
            str(
                result.get(
                    "crowding_side",
                    "",
                )
            )
            .strip()
            .lower()
        )

        same_side = (
            (
                directional_bias
                ==
                TradeBias.LONG
                and
                side == "long"
            )
            or
            (
                directional_bias
                ==
                TradeBias.SHORT
                and
                side == "short"
            )
        )

        return {
            "score":
                score,

            "side":
                side
                or
                "unknown",

            "same_side":
                same_side,

            "same_side_extreme":
                (
                    same_side
                    and
                    score is not None
                    and
                    score
                    >=
                    self.config
                    .extreme_crowding_score
                ),
        }

    # =================================
    # Reasoning
    # =================================

    def _build_reasoning(
        self,
        action: TradeBias,
        directional_bias: TradeBias,
        metrics: DecisionMetrics,
        gates: list[
            DecisionGate
        ],
        payload: DecisionInput,
    ) -> list[
        str
    ]:

        reasoning = [
            (
                "Directional bias: "
                f"{directional_bias.value.upper()} "
                f"with score "
                f"{metrics.directional_score:.3f}."
            ),

            (
                "CHARTS score: "
                f"{metrics.charts_score:.3f}."
                if (
                    metrics.charts_score
                    is not None
                )
                else
                "CHARTS score unavailable."
            ),

            (
                "SENTIMENT score: "
                f"{metrics.sentiment_score:.3f}."
                if (
                    metrics.sentiment_score
                    is not None
                )
                else
                "SENTIMENT score unavailable."
            ),

            (
                "NEWS score: "
                f"{metrics.news_score:.3f}."
                if (
                    metrics.news_score
                    is not None
                )
                else
                "NEWS score unavailable."
            ),
        ]

        failed = [
            gate
            for gate
            in gates
            if (
                gate.status
                ==
                DecisionGateStatus.FAIL
            )
        ]

        if action == TradeBias.WAIT:

            if failed:

                reasoning.append(
                    (
                        "WAIT because blocking "
                        "conditions remain: "
                        +
                        ", ".join(
                            gate.name
                            for gate
                            in failed
                        )
                        +
                        "."
                    )
                )

            else:

                reasoning.append(
                    (
                        "WAIT because current "
                        "conditions do not justify "
                        "an actionable trade."
                    )
                )

        else:

            reasoning.append(
                (
                    f"{action.value.upper()} "
                    "passed all blocking "
                    "decision gates."
                )
            )

        if (
            payload.proposed_trade
            is not None
        ):

            reasoning.append(
                (
                    "Proposed trade: "
                    f"{payload.proposed_trade.side.value.upper()} "
                    f"entry "
                    f"{payload.proposed_trade.entry_price}."
                )
            )

        return reasoning

    # =================================
    # Integrity
    # =================================

    def _validate_symbols(
        self,
        symbol: str,
        payload: DecisionInput,
    ) -> None:

        if (
            payload.proposed_trade
            is not None
        ):

            trade_symbol = (
                self._normalize_symbol(
                    payload
                    .proposed_trade
                    .symbol
                )
            )

            if trade_symbol != symbol:

                raise ValueError(
                    (
                        "Decision symbol mismatch: "
                        f"context={symbol!r}, "
                        "proposed_trade="
                        f"{trade_symbol!r}."
                    )
                )

        for name, result in (
            (
                "news",
                payload.news_result,
            ),
            (
                "sentiment",
                payload.sentiment_result,
            ),
            (
                "charts",
                payload.charts_result,
            ),
            (
                "risk",
                payload.risk_result,
            ),
        ):

            if not result:

                continue

            result_symbol = (
                result.get(
                    "symbol"
                )
            )

            if not result_symbol:

                continue

            normalized = (
                self._normalize_symbol(
                    str(
                        result_symbol
                    )
                )
            )

            if normalized != symbol:

                raise ValueError(
                    (
                        "Decision symbol mismatch: "
                        f"{name}.symbol="
                        f"{normalized!r}, "
                        f"context={symbol!r}."
                    )
                )

    # =================================
    # Helpers
    # =================================

    def _score_to_bias(
        self,
        score: float,
    ) -> TradeBias:

        threshold = (
            self.config
            .minimum_directional_score
        )

        if score >= threshold:

            return TradeBias.LONG

        if score <= -threshold:

            return TradeBias.SHORT

        return TradeBias.NEUTRAL

    @staticmethod
    def _available(
        result: dict[
            str,
            Any,
        ],
    ) -> bool:

        if not result:

            return False

        status = (
            result.get(
                "status"
            )
        )

        if status is None:

            return True

        return (
            str(
                status
            )
            .strip()
            .lower()
            ==
            "success"
        )

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:

        normalized = (
            symbol
            .strip()
            .upper()
        )

        if not normalized:

            raise ValueError(
                "Decision symbol cannot "
                "be empty."
            )

        return normalized

    def _bias_score(
        self,
        result: dict[
            str,
            Any,
        ],
    ) -> (
        float
        | None
    ):

        bias = (
            self._to_bias(
                result.get(
                    "bias"
                )
            )
        )

        sign = (
            self._bias_sign(
                bias
            )
        )

        if sign == 0:

            return 0.0

        confidence = (
            self._safe_float(
                result.get(
                    "confidence"
                )
            )
        )

        if confidence is None:

            confidence = 0.5

        return (
            sign
            *
            self._clamp01(
                confidence
            )
        )

    def _timeframe_bias(
        self,
        analysis: Any,
    ) -> TradeBias:

        if not isinstance(
            analysis,
            dict,
        ):

            return (
                TradeBias.NEUTRAL
            )

        bias = (
            self._to_bias(
                analysis.get(
                    "bias"
                )
            )
        )

        if (
            bias
            in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
        ):

            return bias

        score = (
            self._safe_float(
                analysis.get(
                    "score"
                )
            )
        )

        if score is None:

            return (
                TradeBias.NEUTRAL
            )

        if score >= 0.15:

            return TradeBias.LONG

        if score <= -0.15:

            return TradeBias.SHORT

        return TradeBias.NEUTRAL

    @staticmethod
    def _to_bias(
        value: Any,
    ) -> TradeBias:

        if isinstance(
            value,
            TradeBias,
        ):

            return value

        try:

            return TradeBias(
                str(
                    value
                )
                .strip()
                .lower()
            )

        except (
            TypeError,
            ValueError,
        ):

            return (
                TradeBias.NEUTRAL
            )

    @staticmethod
    def _bias_sign(
        bias: TradeBias,
    ) -> int:

        if bias == TradeBias.LONG:

            return 1

        if bias == TradeBias.SHORT:

            return -1

        return 0

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> (
        float
        | None
    ):

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        return number

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
