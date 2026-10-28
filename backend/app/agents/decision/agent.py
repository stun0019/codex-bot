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
    DecisionAnalyzer,
)

from .models import (
    DecisionInput,
    DecisionMetrics,
    DecisionOutput,
    DecisionSnapshot,
    TradeDecision,
)


class DecisionAgent(
    BaseAgent[
        DecisionInput,
        DecisionOutput,
    ]
):
    """
    Final decision layer.

    DECISION integrates:

        SCOUT
        NEWS
        SENTIMENT
        CHARTS
        RISK

    Final action:

        LONG
        SHORT
        WAIT

    DECISION does not execute trades.
    """

    name = AgentName.DECISION

    def __init__(
        self,
        analyzer: (
            DecisionAnalyzer
            | None
        ) = None,
    ) -> None:

        super().__init__()

        self.analyzer = (
            analyzer
            if analyzer is not None
            else DecisionAnalyzer()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: DecisionInput,
    ) -> DecisionOutput:

        try:

            snapshot = (
                self.analyzer.analyze(
                    symbol=(
                        context.symbol
                    ),
                    payload=payload,
                )
            )

            trade = (
                payload.proposed_trade
            )

            position_size = (
                self._recommended_position_size(
                    payload
                )
            )

            decision = TradeDecision(
                action=(
                    snapshot.action
                ),

                directional_bias=(
                    snapshot
                    .directional_bias
                ),

                symbol=(
                    snapshot.symbol
                ),

                entry_price=(
                    trade.entry_price
                    if trade is not None
                    else None
                ),

                stop_loss=(
                    trade.stop_loss
                    if trade is not None
                    else None
                ),

                take_profit=(
                    trade.take_profit
                    if trade is not None
                    else None
                ),

                position_size=(
                    position_size
                ),

                position_size_unit=(
                    "USDT_NOTIONAL"
                    if position_size
                    is not None
                    else None
                ),

                strategy=(
                    "multi_agent_consensus_v1"
                ),

                reasoning=(
                    snapshot.reasoning
                ),

                gates=(
                    snapshot.gates
                ),
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

            return DecisionOutput(
                agent=self.name,

                status=(
                    AgentStatus.SUCCESS
                ),

                symbol=(
                    snapshot.symbol
                ),

                bias=(
                    snapshot.action
                ),

                directional_bias=(
                    snapshot
                    .directional_bias
                ),

                confidence=(
                    snapshot.confidence
                ),

                summary=summary,

                evidence=evidence,

                risk_approved=(
                    snapshot
                    .risk_approved
                ),

                metrics=(
                    snapshot.metrics
                ),

                gates=(
                    snapshot.gates
                ),

                decision=decision,

                data={
                    "action":
                        snapshot
                        .action
                        .value,

                    "directional_bias":
                        snapshot
                        .directional_bias
                        .value,

                    "risk_approved":
                        snapshot
                        .risk_approved,

                    "directional_score":
                        snapshot
                        .metrics
                        .directional_score,

                    "consensus_score":
                        snapshot
                        .metrics
                        .consensus_score,

                    "disagreement_score":
                        snapshot
                        .metrics
                        .disagreement_score,

                    "data_quality_score":
                        snapshot
                        .metrics
                        .data_quality_score,

                    "blocking_failures": [
                        gate.name
                        for gate
                        in snapshot.gates
                        if (
                            gate.blocking
                            and
                            gate.status.value
                            ==
                            "fail"
                        )
                    ],

                    "strategy":
                        "multi_agent_consensus_v1",

                    "execution":
                        False,
                },

                errors=[],
            )

        except Exception as exc:

            symbol = (
                context.symbol
                .strip()
                .upper()
            )

            decision = TradeDecision(
                action=(
                    TradeBias.WAIT
                ),

                directional_bias=(
                    TradeBias.NEUTRAL
                ),

                symbol=symbol,

                strategy=(
                    "multi_agent_consensus_v1"
                ),

                reasoning=[
                    (
                        "Decision analysis failed: "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                ],
            )

            return DecisionOutput(
                agent=self.name,

                status=(
                    AgentStatus.ERROR
                ),

                symbol=symbol,

                bias=(
                    TradeBias.WAIT
                ),

                directional_bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=0.0,

                summary=(
                    "Decision analysis failed."
                ),

                risk_approved=False,

                metrics=(
                    DecisionMetrics()
                ),

                gates=[],

                decision=decision,

                data={
                    "execution":
                        False,

                    "error_type":
                        type(exc).__name__,

                    "error":
                        str(exc),
                },

                errors=[
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                ],
            )

    @staticmethod
    def _recommended_position_size(
        payload: DecisionInput,
    ) -> (
        float
        | None
    ):

        risk = (
            payload.risk_result
            or {}
        )

        metrics = (
            risk.get(
                "metrics",
                {}
            )
            or {}
        )

        value = (
            metrics.get(
                "recommended_notional_usdt"
            )
        )

        if value is None:

            value = (
                risk.get(
                    "proposed_position_size"
                )
            )

        if (
            value is None
            and
            payload.proposed_trade
            is not None
        ):

            value = (
                payload
                .proposed_trade
                .notional_usdt
            )

        if value is None:

            return None

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _build_evidence(
        snapshot: DecisionSnapshot,
    ) -> list[
        EvidenceItem
    ]:

        evidence: list[
            EvidenceItem
        ] = []

        for gate in snapshot.gates:

            evidence.append(
                EvidenceItem(
                    source=(
                        "decision:"
                        +
                        gate.name
                    ),

                    description=(
                        gate.reason
                    ),

                    value={
                        "status":
                            gate.status.value,

                        "blocking":
                            gate.blocking,

                        "value":
                            gate.value,
                    },
                )
            )

        evidence.append(
            EvidenceItem(
                source=(
                    "decision:composite"
                ),

                description=(
                    "Final multi-agent "
                    "directional composite."
                ),

                value={
                    "action":
                        snapshot
                        .action
                        .value,

                    "directional_bias":
                        snapshot
                        .directional_bias
                        .value,

                    "confidence":
                        snapshot.confidence,

                    "directional_score":
                        snapshot
                        .metrics
                        .directional_score,
                },
            )
        )

        return evidence

    @staticmethod
    def _build_summary(
        snapshot: DecisionSnapshot,
    ) -> str:

        if (
            snapshot.action
            ==
            TradeBias.WAIT
        ):

            return (
                "Decision: WAIT. "
                "Directional bias: "
                f"{snapshot.directional_bias.value.upper()}. "
                "Confidence: "
                f"{snapshot.confidence:.2f}."
            )

        return (
            "Decision: "
            f"{snapshot.action.value.upper()}. "
            "Confidence: "
            f"{snapshot.confidence:.2f}. "
            "Risk approved: "
            f"{snapshot.risk_approved}."
        )
