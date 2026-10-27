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
    RiskAnalyzer,
)

from .models import (
    RiskInput,
    RiskMetrics,
    RiskOutput,
    RiskSnapshot,
    RiskVerdict,
)


class RiskAgent(
    BaseAgent[
        RiskInput,
        RiskOutput,
    ]
):
    """
    Advisory risk analyst.

    RISK 不直接：

        - 下單
        - 平倉
        - 修改 exchange limits
        - 繞過 hard risk engine

    最終交易方向由
    DECISION 負責。
    """

    name = AgentName.RISK

    def __init__(
        self,
        analyzer: (
            RiskAnalyzer
            | None
        ) = None,
    ) -> None:

        super().__init__()

        self.analyzer = (
            analyzer
            if analyzer is not None
            else RiskAnalyzer()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: RiskInput,
    ) -> RiskOutput:

        # =================================
        # No proposed trade
        # =================================

        if (
            payload.proposed_trade
            is None
        ):

            return RiskOutput(
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
                    "No proposed trade "
                    "was supplied for "
                    "risk analysis."
                ),

                approved=False,

                verdict=(
                    RiskVerdict.REVIEW
                ),

                checks=[],

                metrics=(
                    RiskMetrics()
                ),

                recommendations=[
                    (
                        "Provide a proposed "
                        "trade before running "
                        "RISK."
                    )
                ],

                data={
                    "reason":
                        "no_proposed_trade",

                    "hard_risk_engine":
                        False,

                    "advisory_analysis":
                        True,
                },

                errors=[],
            )

        trade = (
            payload.proposed_trade
        )

        # =================================
        # Symbol consistency guard
        # =================================
        #
        # MarketContext 是這次分析的
        # canonical market scope。
        #
        # 如果：
        #
        # context.symbol
        #     !=
        # proposed_trade.symbol
        #
        # 就不能繼續進 RiskAnalyzer。
        #
        # 否則可能出現：
        #
        # 分析 UNI position
        # 卻輸出 BTC symbol
        #
        # 這屬於 input consistency error，
        # 不是正常的 risk REJECT。
        # =================================

        context_symbol = (
            self._normalize_symbol(
                context.symbol
            )
        )

        trade_symbol = (
            self._normalize_symbol(
                trade.symbol
            )
        )

        if (
            context_symbol
            !=
            trade_symbol
        ):

            message = (
                "Risk symbol mismatch: "
                f"context.symbol={context_symbol!r}, "
                "proposed_trade.symbol="
                f"{trade_symbol!r}."
            )

            return RiskOutput(
                agent=self.name,

                status=(
                    AgentStatus.ERROR
                ),

                symbol=(
                    context_symbol
                ),

                bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=0.0,

                summary=(
                    "Risk analysis rejected "
                    "because MarketContext "
                    "and ProposedTrade refer "
                    "to different symbols."
                ),

                approved=False,

                verdict=(
                    RiskVerdict.REVIEW
                ),

                checks=[],

                metrics=(
                    RiskMetrics()
                ),

                recommendations=[
                    (
                        "Use the same symbol "
                        "for MarketContext and "
                        "ProposedTrade before "
                        "running RISK."
                    )
                ],

                data={
                    "reason":
                        "symbol_mismatch",

                    "context_symbol":
                        context_symbol,

                    "proposed_trade_symbol":
                        trade_symbol,

                    "hard_risk_engine":
                        False,

                    "advisory_analysis":
                        True,
                },

                errors=[
                    message
                ],
            )

        # =================================
        # Risk analysis
        # =================================

        try:

            snapshot = (
                self.analyzer.analyze(
                    symbol=(
                        context_symbol
                    ),
                    payload=payload,
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

            return RiskOutput(
                agent=self.name,

                status=(
                    AgentStatus.SUCCESS
                ),

                symbol=(
                    context_symbol
                ),

                bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=(
                    snapshot.confidence
                ),

                summary=summary,

                evidence=evidence,

                approved=(
                    snapshot.approved
                ),

                verdict=(
                    snapshot.verdict
                ),

                checks=(
                    snapshot.checks
                ),

                metrics=(
                    snapshot.metrics
                ),

                recommendations=(
                    snapshot
                    .recommendations
                ),

                proposed_position_size=(
                    snapshot
                    .metrics
                    .recommended_notional_usdt
                ),

                estimated_loss=(
                    snapshot
                    .metrics
                    .estimated_loss_usdt
                ),

                estimated_reward=(
                    snapshot
                    .metrics
                    .estimated_reward_usdt
                ),

                data={
                    "verdict":
                        snapshot
                        .verdict
                        .value,

                    "approved":
                        snapshot
                        .approved,

                    "overall_risk_score":
                        snapshot
                        .metrics
                        .overall_risk_score,

                    "data_quality_score":
                        snapshot
                        .metrics
                        .data_quality_score,

                    "recommended_notional_usdt":
                        snapshot
                        .metrics
                        .recommended_notional_usdt,

                    "failed_checks": [
                        check.name
                        for check
                        in snapshot.checks
                        if not check.passed
                    ],

                    "context_symbol":
                        context_symbol,

                    "proposed_trade_symbol":
                        trade_symbol,

                    "hard_risk_engine":
                        False,

                    "advisory_analysis":
                        True,
                },

                errors=[],
            )

        except Exception as exc:

            return RiskOutput(
                agent=self.name,

                status=(
                    AgentStatus.ERROR
                ),

                symbol=(
                    context_symbol
                ),

                bias=(
                    TradeBias.NEUTRAL
                ),

                confidence=0.0,

                summary=(
                    "Risk analysis failed."
                ),

                approved=False,

                verdict=(
                    RiskVerdict.REVIEW
                ),

                checks=[],

                metrics=(
                    RiskMetrics()
                ),

                recommendations=[],

                data={
                    "reason":
                        "analysis_error",

                    "context_symbol":
                        context_symbol,

                    "proposed_trade_symbol":
                        trade_symbol,

                    "hard_risk_engine":
                        False,

                    "advisory_analysis":
                        True,
                },

                errors=[
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                ],
            )

    # =================================
    # Symbol
    # =================================

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """
        RISK 內部統一 symbol。

        Example:

            " uni-usdt-swap "
                ↓
            "UNI-USDT-SWAP"
        """

        normalized = (
            symbol
            .strip()
            .upper()
        )

        if not normalized:

            raise ValueError(
                "Risk symbol cannot "
                "be empty."
            )

        return normalized

    # =================================
    # Evidence
    # =================================

    @staticmethod
    def _build_evidence(
        snapshot: RiskSnapshot,
    ) -> list[
        EvidenceItem
    ]:

        return [
            EvidenceItem(
                source=(
                    "risk:"
                    +
                    check.category.value
                ),

                description=(
                    check.reason
                    or
                    check.name
                ),

                value={
                    "name":
                        check.name,

                    "passed":
                        check.passed,

                    "severity":
                        check
                        .severity
                        .value,

                    "blocking":
                        check.blocking,

                    "value":
                        check.value,

                    "limit":
                        check.limit,
                },
            )
            for check
            in snapshot.checks
        ]

    # =================================
    # Summary
    # =================================

    @staticmethod
    def _build_summary(
        snapshot: RiskSnapshot,
    ) -> str:

        metrics = (
            snapshot.metrics
        )

        parts = [
            (
                "Risk verdict: "
                +
                snapshot
                .verdict
                .value
                .upper()
                +
                "."
            )
        ]

        if (
            metrics.risk_pct_equity
            is not None
        ):

            parts.append(
                (
                    "Estimated stop risk "
                    f"{metrics.risk_pct_equity:.2f}% "
                    "of equity."
                )
            )

        if (
            metrics.risk_reward_ratio
            is not None
        ):

            parts.append(
                (
                    "Risk/reward "
                    f"{metrics.risk_reward_ratio:.2f}."
                )
            )

        if (
            metrics
            .recommended_notional_usdt
            is not None
        ):

            parts.append(
                (
                    "Recommended notional "
                    f"{metrics.recommended_notional_usdt:.2f} "
                    "USDT or less."
                )
            )

        return " ".join(
            parts
        )
