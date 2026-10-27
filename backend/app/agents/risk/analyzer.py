from __future__ import annotations

from dataclasses import dataclass

from typing import Any

from ..models import (
    TradeBias,
)

from .models import (
    OpenPosition,
    ProposedTrade,
    RiskCategory,
    RiskCheck,
    RiskInput,
    RiskMetrics,
    RiskSeverity,
    RiskSnapshot,
    RiskVerdict,
)


@dataclass(slots=True)
class RiskAnalyzerConfig:
    charts_confidence_threshold: float = 0.55

    crowding_threshold: float = 0.75

    news_impact_threshold: float = 0.70

    high_volatility_leverage_fraction: float = 0.50


class RiskAnalyzer:
    """
    Deterministic advisory risk analyzer.

    不負責：

        - exchange hard limits
        - liquidation protection
        - order execution
        - final trade decision

    這些必須由：

        deterministic risk engine
        DECISION
        execution layer

    分開處理。
    """

    def __init__(
        self,
        config: (
            RiskAnalyzerConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else RiskAnalyzerConfig()
        )

    def analyze(
        self,
        symbol: str,
        payload: RiskInput,
    ) -> RiskSnapshot:

        trade = (
            payload.proposed_trade
        )

        if trade is None:

            return RiskSnapshot(
                symbol=symbol,

                verdict=(
                    RiskVerdict.REVIEW
                ),

                approved=False,

                confidence=0.0,

                recommendations=[
                    (
                        "No proposed trade "
                        "was supplied."
                    )
                ],

                metadata={
                    "reason":
                        "no_proposed_trade",
                },
            )

        limits = (
            payload.risk_limits
        )

        checks: list[
            RiskCheck
        ] = []

        recommendations: list[
            str
        ] = []

        equity = (
            payload.account_equity
        )

        notional = (
            self._resolve_trade_notional(
                trade
            )
        )

        stop_valid = (
            self._valid_stop_direction(
                trade
            )
        )

        target_valid = (
            self._valid_target_direction(
                trade
            )
        )

        stop_distance_pct = (
            self._distance_pct(
                trade.entry_price,
                trade.stop_loss,
            )
            if (
                trade.stop_loss
                is not None
            )
            else None
        )

        target_distance_pct = (
            self._distance_pct(
                trade.entry_price,
                trade.take_profit,
            )
            if (
                trade.take_profit
                is not None
            )
            else None
        )

        estimated_loss = None
        estimated_reward = None
        risk_pct_equity = None
        risk_reward_ratio = None
        margin_required = None
        position_exposure_pct = None

        if (
            notional is not None
        ):

            margin_required = (
                notional
                /
                trade.leverage
            )

        if (
            notional is not None
            and stop_distance_pct
            is not None
            and stop_valid
        ):

            estimated_loss = (
                notional
                *
                stop_distance_pct
                /
                100.0
            )

        if (
            notional is not None
            and target_distance_pct
            is not None
            and target_valid
        ):

            estimated_reward = (
                notional
                *
                target_distance_pct
                /
                100.0
            )

        if (
            equity is not None
            and estimated_loss
            is not None
        ):

            risk_pct_equity = (
                estimated_loss
                /
                equity
                *
                100.0
            )

        if (
            estimated_loss is not None
            and estimated_loss > 0
            and estimated_reward
            is not None
        ):

            risk_reward_ratio = (
                estimated_reward
                /
                estimated_loss
            )

        if (
            equity is not None
            and notional is not None
        ):

            position_exposure_pct = (
                notional
                /
                equity
                *
                100.0
            )

        existing_total = sum(
            self._resolve_position_notional(
                position
            )
            for position
            in payload.open_positions
        )

        existing_symbol = sum(
            self._resolve_position_notional(
                position
            )
            for position
            in payload.open_positions
            if (
                position.symbol.upper()
                ==
                trade.symbol.upper()
            )
        )

        total_exposure_before_pct = (
            (
                existing_total
                /
                equity
                *
                100.0
            )
            if (
                equity is not None
                and equity > 0
            )
            else None
        )

        total_after = (
            existing_total
            +
            (
                notional
                or 0.0
            )
        )

        symbol_after = (
            existing_symbol
            +
            (
                notional
                or 0.0
            )
        )

        total_exposure_after_pct = (
            (
                total_after
                /
                equity
                *
                100.0
            )
            if (
                equity is not None
                and equity > 0
            )
            else None
        )

        symbol_exposure_after_pct = (
            (
                symbol_after
                /
                equity
                *
                100.0
            )
            if (
                equity is not None
                and equity > 0
            )
            else None
        )

        daily_drawdown_pct = None

        if (
            equity is not None
            and payload.daily_pnl
            is not None
            and payload.daily_pnl < 0
        ):

            daily_drawdown_pct = (
                abs(
                    payload.daily_pnl
                )
                /
                equity
                *
                100.0
            )

        # =============================
        # Core checks
        # =============================

        checks.append(
            RiskCheck(
                name="account_equity",

                category=(
                    RiskCategory.ACCOUNT
                ),

                passed=(
                    equity is not None
                    and equity > 0
                ),

                severity=(
                    RiskSeverity.CRITICAL
                ),

                blocking=True,

                reason=(
                    "Account equity is available."
                    if equity is not None
                    else (
                        "Account equity is required "
                        "for position risk analysis."
                    )
                ),

                value=equity,
            )
        )

        checks.append(
            RiskCheck(
                name="position_notional",

                category=(
                    RiskCategory.POSITION
                ),

                passed=(
                    notional is not None
                    and notional > 0
                ),

                severity=(
                    RiskSeverity.CRITICAL
                ),

                blocking=True,

                reason=(
                    "Position notional is available."
                    if notional is not None
                    else (
                        "Provide notional_usdt "
                        "or quantity."
                    )
                ),

                value=notional,
            )
        )

        checks.append(
            RiskCheck(
                name="stop_loss_present",

                category=(
                    RiskCategory.STOP
                ),

                passed=(
                    trade.stop_loss
                    is not None
                ),

                severity=(
                    RiskSeverity.CRITICAL
                ),

                blocking=True,

                reason=(
                    "Stop loss is defined."
                    if trade.stop_loss
                    is not None
                    else (
                        "A stop loss is required "
                        "for risk estimation."
                    )
                ),

                value=(
                    trade.stop_loss
                ),
            )
        )

        checks.append(
            RiskCheck(
                name="stop_direction",

                category=(
                    RiskCategory.STOP
                ),

                passed=(
                    stop_valid
                ),

                severity=(
                    RiskSeverity.CRITICAL
                ),

                blocking=True,

                reason=(
                    "Stop loss is on the "
                    "correct invalidation side."
                    if stop_valid
                    else (
                        "LONG stop must be below "
                        "entry; SHORT stop must "
                        "be above entry."
                    )
                ),

                value=(
                    trade.stop_loss
                ),
            )
        )

        checks.append(
            RiskCheck(
                name="leverage",

                category=(
                    RiskCategory.LEVERAGE
                ),

                passed=(
                    trade.leverage
                    <=
                    limits.max_leverage
                ),

                severity=(
                    RiskSeverity.CRITICAL
                ),

                blocking=True,

                reason=(
                    "Leverage is within "
                    "configured limit."
                    if (
                        trade.leverage
                        <=
                        limits.max_leverage
                    )
                    else (
                        "Leverage exceeds "
                        "configured limit."
                    )
                ),

                value=(
                    trade.leverage
                ),

                limit=(
                    limits.max_leverage
                ),
            )
        )

        if (
            position_exposure_pct
            is not None
        ):

            checks.append(
                RiskCheck(
                    name=(
                        "position_exposure"
                    ),

                    category=(
                        RiskCategory.EXPOSURE
                    ),

                    passed=(
                        position_exposure_pct
                        <=
                        limits
                        .max_position_notional_pct
                    ),

                    severity=(
                        RiskSeverity.HIGH
                    ),

                    blocking=True,

                    reason=(
                        "Single-position exposure "
                        "is within limit."
                        if (
                            position_exposure_pct
                            <=
                            limits
                            .max_position_notional_pct
                        )
                        else (
                            "Single-position exposure "
                            "is too large."
                        )
                    ),

                    value=(
                        position_exposure_pct
                    ),

                    limit=(
                        limits
                        .max_position_notional_pct
                    ),
                )
            )

        if (
            symbol_exposure_after_pct
            is not None
        ):

            checks.append(
                RiskCheck(
                    name="symbol_exposure",

                    category=(
                        RiskCategory.EXPOSURE
                    ),

                    passed=(
                        symbol_exposure_after_pct
                        <=
                        limits
                        .max_symbol_exposure_pct
                    ),

                    severity=(
                        RiskSeverity.HIGH
                    ),

                    blocking=True,

                    reason=(
                        "Symbol exposure is "
                        "within limit."
                        if (
                            symbol_exposure_after_pct
                            <=
                            limits
                            .max_symbol_exposure_pct
                        )
                        else (
                            "Combined exposure to "
                            "this symbol is too large."
                        )
                    ),

                    value=(
                        symbol_exposure_after_pct
                    ),

                    limit=(
                        limits
                        .max_symbol_exposure_pct
                    ),
                )
            )

        if (
            total_exposure_after_pct
            is not None
        ):

            checks.append(
                RiskCheck(
                    name="total_exposure",

                    category=(
                        RiskCategory.EXPOSURE
                    ),

                    passed=(
                        total_exposure_after_pct
                        <=
                        limits
                        .max_total_exposure_pct
                    ),

                    severity=(
                        RiskSeverity.CRITICAL
                    ),

                    blocking=True,

                    reason=(
                        "Total portfolio exposure "
                        "is within limit."
                        if (
                            total_exposure_after_pct
                            <=
                            limits
                            .max_total_exposure_pct
                        )
                        else (
                            "Total portfolio exposure "
                            "would exceed limit."
                        )
                    ),

                    value=(
                        total_exposure_after_pct
                    ),

                    limit=(
                        limits
                        .max_total_exposure_pct
                    ),
                )
            )

        if (
            risk_pct_equity
            is not None
        ):

            checks.append(
                RiskCheck(
                    name="risk_per_trade",

                    category=(
                        RiskCategory.POSITION
                    ),

                    passed=(
                        risk_pct_equity
                        <=
                        limits
                        .max_risk_per_trade_pct
                    ),

                    severity=(
                        RiskSeverity.CRITICAL
                    ),

                    blocking=True,

                    reason=(
                        "Estimated stop-loss risk "
                        "is within limit."
                        if (
                            risk_pct_equity
                            <=
                            limits
                            .max_risk_per_trade_pct
                        )
                        else (
                            "Estimated loss at stop "
                            "exceeds per-trade risk "
                            "limit."
                        )
                    ),

                    value=(
                        risk_pct_equity
                    ),

                    limit=(
                        limits
                        .max_risk_per_trade_pct
                    ),
                )
            )

        if (
            stop_distance_pct
            is not None
        ):

            checks.append(
                RiskCheck(
                    name="stop_distance",

                    category=(
                        RiskCategory.STOP
                    ),

                    passed=(
                        stop_distance_pct
                        <=
                        limits
                        .max_stop_distance_pct
                    ),

                    severity=(
                        RiskSeverity.MEDIUM
                    ),

                    blocking=True,

                    reason=(
                        "Stop distance is within "
                        "configured range."
                        if (
                            stop_distance_pct
                            <=
                            limits
                            .max_stop_distance_pct
                        )
                        else (
                            "Stop distance is wider "
                            "than configured limit."
                        )
                    ),

                    value=(
                        stop_distance_pct
                    ),

                    limit=(
                        limits
                        .max_stop_distance_pct
                    ),
                )
            )

        # =============================
        # Margin
        # =============================

        if (
            payload.available_balance
            is not None
            and equity is not None
            and margin_required
            is not None
        ):

            reserve = (
                equity
                *
                limits
                .min_free_balance_pct
                /
                100.0
            )

            remaining = (
                payload.available_balance
                -
                margin_required
            )

            margin_ok = (
                remaining
                >=
                reserve
            )

            checks.append(
                RiskCheck(
                    name="available_margin",

                    category=(
                        RiskCategory.ACCOUNT
                    ),

                    passed=(
                        margin_ok
                    ),

                    severity=(
                        RiskSeverity.CRITICAL
                    ),

                    blocking=True,

                    reason=(
                        "Available balance retains "
                        "configured free reserve."
                        if margin_ok
                        else (
                            "Trade would consume too "
                            "much available margin."
                        )
                    ),

                    value={
                        "required_margin":
                            margin_required,

                        "remaining_balance":
                            remaining,
                    },

                    limit={
                        "minimum_reserve":
                            reserve,
                    },
                )
            )

        # =============================
        # Daily drawdown
        # =============================

        if (
            daily_drawdown_pct
            is not None
        ):

            checks.append(
                RiskCheck(
                    name="daily_loss",

                    category=(
                        RiskCategory.DAILY_LOSS
                    ),

                    passed=(
                        daily_drawdown_pct
                        <=
                        limits
                        .max_daily_loss_pct
                    ),

                    severity=(
                        RiskSeverity.CRITICAL
                    ),

                    blocking=True,

                    reason=(
                        "Daily drawdown is "
                        "within limit."
                        if (
                            daily_drawdown_pct
                            <=
                            limits
                            .max_daily_loss_pct
                        )
                        else (
                            "Daily loss limit "
                            "has been exceeded."
                        )
                    ),

                    value=(
                        daily_drawdown_pct
                    ),

                    limit=(
                        limits
                        .max_daily_loss_pct
                    ),
                )
            )

        # =============================
        # Reward
        # =============================

        if (
            trade.take_profit
            is None
        ):

            checks.append(
                RiskCheck(
                    name="risk_reward",

                    category=(
                        RiskCategory.REWARD
                    ),

                    passed=False,

                    severity=(
                        RiskSeverity.MEDIUM
                    ),

                    blocking=False,

                    reason=(
                        "No take-profit target "
                        "was supplied."
                    ),
                )
            )

            recommendations.append(
                (
                    "Define a target before "
                    "final trade approval."
                )
            )

        elif not target_valid:

            checks.append(
                RiskCheck(
                    name="target_direction",

                    category=(
                        RiskCategory.REWARD
                    ),

                    passed=False,

                    severity=(
                        RiskSeverity.HIGH
                    ),

                    blocking=True,

                    reason=(
                        "Take-profit target is "
                        "on the wrong side of entry."
                    ),

                    value=(
                        trade.take_profit
                    ),
                )
            )

        elif (
            risk_reward_ratio
            is not None
        ):

            checks.append(
                RiskCheck(
                    name="risk_reward",

                    category=(
                        RiskCategory.REWARD
                    ),

                    passed=(
                        risk_reward_ratio
                        >=
                        limits.min_risk_reward
                    ),

                    severity=(
                        RiskSeverity.MEDIUM
                    ),

                    blocking=True,

                    reason=(
                        "Risk/reward ratio meets "
                        "configured minimum."
                        if (
                            risk_reward_ratio
                            >=
                            limits.min_risk_reward
                        )
                        else (
                            "Risk/reward ratio is "
                            "below configured minimum."
                        )
                    ),

                    value=(
                        risk_reward_ratio
                    ),

                    limit=(
                        limits.min_risk_reward
                    ),
                )
            )

        # =============================
        # CHARTS
        # =============================

        if payload.charts_result:

            charts_check = (
                self._analyze_charts_risk(
                    trade=trade,
                    result=(
                        payload
                        .charts_result
                    ),
                    limits=limits,
                )
            )

            checks.extend(
                charts_check
            )

        # =============================
        # SENTIMENT
        # =============================

        if payload.sentiment_result:

            sentiment_check = (
                self
                ._analyze_sentiment_risk(
                    trade=trade,
                    result=(
                        payload
                        .sentiment_result
                    ),
                )
            )

            if (
                sentiment_check
                is not None
            ):

                checks.append(
                    sentiment_check
                )

        # =============================
        # NEWS
        # =============================

        if payload.news_result:

            news_check = (
                self._analyze_news_risk(
                    trade=trade,
                    result=(
                        payload.news_result
                    ),
                )
            )

            if news_check is not None:

                checks.append(
                    news_check
                )

        recommended_notional = (
            self._recommended_notional(
                payload=payload,
                trade=trade,
                current_notional=notional,
                stop_distance_pct=(
                    stop_distance_pct
                ),
                existing_total=(
                    existing_total
                ),
                existing_symbol=(
                    existing_symbol
                ),
            )
        )

        if (
            notional is not None
            and recommended_notional
            is not None
            and recommended_notional
            <
            notional
            *
            0.99
        ):

            recommendations.append(
                (
                    "Reduce proposed notional "
                    f"from {notional:.2f} USDT "
                    "to approximately "
                    f"{recommended_notional:.2f} "
                    "USDT or less."
                )
            )

        data_quality = (
            self._data_quality(
                payload
            )
        )

        risk_score = (
            self._overall_risk_score(
                trade=trade,
                payload=payload,
                risk_pct_equity=(
                    risk_pct_equity
                ),
                position_exposure_pct=(
                    position_exposure_pct
                ),
                total_exposure_after_pct=(
                    total_exposure_after_pct
                ),
                daily_drawdown_pct=(
                    daily_drawdown_pct
                ),
            )
        )

        verdict = (
            self._resolve_verdict(
                checks=checks,
                data_quality=(
                    data_quality
                ),
            )
        )

        approved = (
            verdict
            ==
            RiskVerdict.APPROVE
        )

        confidence = (
            self._confidence(
                checks=checks,
                data_quality=(
                    data_quality
                ),
            )
        )

        if verdict == RiskVerdict.APPROVE:

            recommendations.insert(
                0,
                (
                    "Risk profile is within "
                    "configured advisory limits."
                )
            )

        elif verdict == RiskVerdict.REDUCE:

            recommendations.insert(
                0,
                (
                    "Reduce or revise the trade "
                    "before final approval."
                )
            )

        elif verdict == RiskVerdict.REJECT:

            recommendations.insert(
                0,
                (
                    "Do not approve this trade "
                    "until critical failures "
                    "are resolved."
                )
            )

        else:

            recommendations.insert(
                0,
                (
                    "Additional information is "
                    "required before approval."
                )
            )

        metrics = RiskMetrics(
            notional_usdt=(
                notional
            ),

            margin_required_usdt=(
                margin_required
            ),

            stop_distance_pct=(
                stop_distance_pct
            ),

            target_distance_pct=(
                target_distance_pct
            ),

            estimated_loss_usdt=(
                estimated_loss
            ),

            estimated_reward_usdt=(
                estimated_reward
            ),

            risk_pct_equity=(
                risk_pct_equity
            ),

            risk_reward_ratio=(
                risk_reward_ratio
            ),

            position_exposure_pct=(
                position_exposure_pct
            ),

            symbol_exposure_after_pct=(
                symbol_exposure_after_pct
            ),

            total_exposure_before_pct=(
                total_exposure_before_pct
            ),

            total_exposure_after_pct=(
                total_exposure_after_pct
            ),

            daily_drawdown_pct=(
                daily_drawdown_pct
            ),

            recommended_notional_usdt=(
                recommended_notional
            ),

            overall_risk_score=(
                risk_score
            ),

            data_quality_score=(
                data_quality
            ),
        )

        return RiskSnapshot(
            symbol=symbol,

            verdict=verdict,

            approved=approved,

            confidence=confidence,

            metrics=metrics,

            checks=checks,

            recommendations=(
                recommendations
            ),

            metadata={
                "hard_risk_engine":
                    False,

                "advisory_analysis":
                    True,

                "open_position_count":
                    len(
                        payload
                        .open_positions
                    ),
            },
        )

    # =================================
    # Market evidence
    # =================================

    def _analyze_charts_risk(
        self,
        trade: ProposedTrade,
        result: dict[str, Any],
        limits,
    ) -> list[
        RiskCheck
    ]:

        checks: list[
            RiskCheck
        ] = []

        bias = (
            self._to_bias(
                result.get(
                    "bias"
                )
            )
        )

        confidence = (
            self._safe_float(
                result.get(
                    "confidence"
                )
            )
            or 0.0
        )

        if (
            bias
            in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
            and confidence
            >=
            self.config
            .charts_confidence_threshold
        ):

            aligned = (
                bias
                ==
                trade.side
            )

            checks.append(
                RiskCheck(
                    name="charts_alignment",

                    category=(
                        RiskCategory.CHARTS
                    ),

                    passed=aligned,

                    severity=(
                        RiskSeverity.HIGH
                    ),

                    blocking=False,

                    reason=(
                        "CHARTS bias is aligned "
                        "with proposed direction."
                        if aligned
                        else (
                            "High-confidence CHARTS "
                            "bias opposes the "
                            "proposed direction."
                        )
                    ),

                    value={
                        "charts_bias":
                            bias.value,

                        "confidence":
                            confidence,
                    },
                )
            )

        volatility = str(
            result.get(
                "volatility_regime",
                ""
            )
        ).lower()

        if (
            "high"
            in volatility
        ):

            threshold = max(
                1.0,
                limits.max_leverage
                *
                self.config
                .high_volatility_leverage_fraction,
            )

            passed = (
                trade.leverage
                <=
                threshold
            )

            checks.append(
                RiskCheck(
                    name=(
                        "high_volatility_leverage"
                    ),

                    category=(
                        RiskCategory.CHARTS
                    ),

                    passed=passed,

                    severity=(
                        RiskSeverity.HIGH
                    ),

                    blocking=False,

                    reason=(
                        "Leverage is restrained "
                        "for high volatility."
                        if passed
                        else (
                            "High volatility combined "
                            "with elevated leverage "
                            "increases risk."
                        )
                    ),

                    value=(
                        trade.leverage
                    ),

                    limit=(
                        threshold
                    ),
                )
            )

        return checks

    def _analyze_sentiment_risk(
        self,
        trade: ProposedTrade,
        result: dict[str, Any],
    ) -> (
        RiskCheck
        | None
    ):

        metrics = (
            result.get(
                "metrics",
                {}
            )
            or {}
        )

        crowding_score = (
            self._safe_float(
                metrics.get(
                    "crowding_score"
                )
            )
        )

        crowding_side = str(
            result.get(
                "crowding_side",
                ""
            )
        ).lower()

        if crowding_score is None:

            return None

        same_side = (
            (
                trade.side
                ==
                TradeBias.LONG
                and
                "long"
                in crowding_side
            )
            or
            (
                trade.side
                ==
                TradeBias.SHORT
                and
                "short"
                in crowding_side
            )
        )

        risky = (
            same_side
            and
            crowding_score
            >=
            self.config
            .crowding_threshold
        )

        return RiskCheck(
            name="sentiment_crowding",

            category=(
                RiskCategory.SENTIMENT
            ),

            passed=(
                not risky
            ),

            severity=(
                RiskSeverity.HIGH
                if risky
                else RiskSeverity.LOW
            ),

            blocking=False,

            reason=(
                "Proposed trade is entering "
                "the same side as an "
                "extremely crowded market."
                if risky
                else (
                    "No extreme same-side "
                    "crowding risk detected."
                )
            ),

            value={
                "crowding_score":
                    crowding_score,

                "crowding_side":
                    crowding_side,
            },
        )

    def _analyze_news_risk(
        self,
        trade: ProposedTrade,
        result: dict[str, Any],
    ) -> (
        RiskCheck
        | None
    ):

        events = (
            result.get(
                "events",
                []
            )
            or []
        )

        highest_risk = None

        for event in events:

            if not isinstance(
                event,
                dict,
            ):

                continue

            affected = (
                event.get(
                    "affected_symbols",
                    []
                )
                or []
            )

            if (
                affected
                and
                trade.symbol
                not in affected
            ):

                continue

            bias = (
                self._to_bias(
                    event.get(
                        "bias"
                    )
                )
            )

            impact = (
                self._safe_float(
                    event.get(
                        "impact_score"
                    )
                )
                or 0.0
            )

            opposite = (
                bias
                in (
                    TradeBias.LONG,
                    TradeBias.SHORT,
                )
                and
                bias
                !=
                trade.side
            )

            if (
                opposite
                and
                impact
                >=
                self.config
                .news_impact_threshold
            ):

                if (
                    highest_risk
                    is None
                    or
                    impact
                    >
                    highest_risk[
                        "impact"
                    ]
                ):

                    highest_risk = {
                        "impact":
                            impact,

                        "bias":
                            bias,

                        "title":
                            event.get(
                                "title",
                                "",
                            ),
                    }

        if highest_risk is None:

            return RiskCheck(
                name="news_event_risk",

                category=(
                    RiskCategory.NEWS
                ),

                passed=True,

                severity=(
                    RiskSeverity.LOW
                ),

                blocking=False,

                reason=(
                    "No high-impact opposite "
                    "news event detected."
                ),
            )

        return RiskCheck(
            name="news_event_risk",

            category=(
                RiskCategory.NEWS
            ),

            passed=False,

            severity=(
                RiskSeverity.HIGH
            ),

            blocking=False,

            reason=(
                "A high-impact news event "
                "opposes the proposed trade."
            ),

            value={
                "title":
                    highest_risk[
                        "title"
                    ],

                "impact_score":
                    highest_risk[
                        "impact"
                    ],

                "bias":
                    highest_risk[
                        "bias"
                    ].value,
            },
        )

    # =================================
    # Position sizing
    # =================================

    def _recommended_notional(
        self,
        payload: RiskInput,
        trade: ProposedTrade,
        current_notional: (
            float
            | None
        ),
        stop_distance_pct: (
            float
            | None
        ),
        existing_total: float,
        existing_symbol: float,
    ) -> (
        float
        | None
    ):

        equity = (
            payload.account_equity
        )

        if (
            equity is None
            or equity <= 0
        ):

            return None

        limits = (
            payload.risk_limits
        )

        caps: list[
            float
        ] = []

        caps.append(
            equity
            *
            limits
            .max_position_notional_pct
            /
            100.0
        )

        caps.append(
            max(
                0.0,
                equity
                *
                limits
                .max_symbol_exposure_pct
                /
                100.0
                -
                existing_symbol,
            )
        )

        caps.append(
            max(
                0.0,
                equity
                *
                limits
                .max_total_exposure_pct
                /
                100.0
                -
                existing_total,
            )
        )

        if (
            stop_distance_pct
            is not None
            and stop_distance_pct
            > 0
        ):

            risk_budget = (
                equity
                *
                limits
                .max_risk_per_trade_pct
                /
                100.0
            )

            risk_based_notional = (
                risk_budget
                /
                (
                    stop_distance_pct
                    /
                    100.0
                )
            )

            caps.append(
                risk_based_notional
            )

        if (
            payload.available_balance
            is not None
        ):

            usable_margin = (
                payload
                .available_balance
                *
                (
                    1.0
                    -
                    limits
                    .min_free_balance_pct
                    /
                    100.0
                )
            )

            caps.append(
                max(
                    0.0,
                    usable_margin
                    *
                    trade.leverage,
                )
            )

        recommended = min(
            caps
        )

        if (
            current_notional
            is not None
        ):

            recommended = min(
                recommended,
                current_notional,
            )

        return max(
            0.0,
            recommended,
        )

    # =================================
    # Verdict
    # =================================

    @staticmethod
    def _resolve_verdict(
        checks: list[
            RiskCheck
        ],
        data_quality: float,
    ) -> RiskVerdict:

        failed = [
            check
            for check
            in checks
            if not check.passed
        ]

        if any(
            check.severity
            ==
            RiskSeverity.CRITICAL
            for check
            in failed
        ):

            return (
                RiskVerdict.REJECT
            )

        if any(
            check.blocking
            for check
            in failed
        ):

            return (
                RiskVerdict.REDUCE
            )

        if any(
            check.severity
            ==
            RiskSeverity.HIGH
            for check
            in failed
        ):

            return (
                RiskVerdict.REDUCE
            )

        if data_quality < 0.50:

            return (
                RiskVerdict.REVIEW
            )

        return (
            RiskVerdict.APPROVE
        )

    @staticmethod
    def _confidence(
        checks: list[
            RiskCheck
        ],
        data_quality: float,
    ) -> float:

        if not checks:

            return 0.0

        failed_count = sum(
            1
            for check
            in checks
            if not check.passed
        )

        penalty = (
            failed_count
            /
            len(
                checks
            )
            *
            0.25
        )

        return max(
            0.0,
            min(
                1.0,
                data_quality
                *
                (
                    1.0
                    -
                    penalty
                ),
            ),
        )

    @staticmethod
    def _data_quality(
        payload: RiskInput,
    ) -> float:

        trade = (
            payload.proposed_trade
        )

        if trade is None:

            return 0.0

        score = 0.0

        if (
            payload.account_equity
            is not None
        ):
            score += 0.20

        if (
            trade.notional_usdt
            is not None
            or trade.quantity
            is not None
        ):
            score += 0.15

        if (
            trade.stop_loss
            is not None
        ):
            score += 0.20

        if (
            trade.take_profit
            is not None
        ):
            score += 0.10

        if (
            payload.available_balance
            is not None
        ):
            score += 0.10

        if payload.charts_result:
            score += 0.10

        if payload.sentiment_result:
            score += 0.075

        if payload.news_result:
            score += 0.075

        return max(
            0.0,
            min(
                1.0,
                score,
            ),
        )

    @staticmethod
    def _overall_risk_score(
        trade: ProposedTrade,
        payload: RiskInput,
        risk_pct_equity: (
            float
            | None
        ),
        position_exposure_pct: (
            float
            | None
        ),
        total_exposure_after_pct: (
            float
            | None
        ),
        daily_drawdown_pct: (
            float
            | None
        ),
    ) -> float:

        limits = (
            payload.risk_limits
        )

        values: list[
            float
        ] = [
            trade.leverage
            /
            limits.max_leverage
        ]

        if (
            risk_pct_equity
            is not None
        ):

            values.append(
                risk_pct_equity
                /
                limits
                .max_risk_per_trade_pct
            )

        if (
            position_exposure_pct
            is not None
        ):

            values.append(
                position_exposure_pct
                /
                limits
                .max_position_notional_pct
            )

        if (
            total_exposure_after_pct
            is not None
        ):

            values.append(
                total_exposure_after_pct
                /
                limits
                .max_total_exposure_pct
            )

        if (
            daily_drawdown_pct
            is not None
        ):

            values.append(
                daily_drawdown_pct
                /
                limits
                .max_daily_loss_pct
            )

        if not values:

            return 0.0

        return max(
            0.0,
            min(
                1.0,
                max(
                    values
                ),
            ),
        )

    # =================================
    # Helpers
    # =================================

    @staticmethod
    def _resolve_trade_notional(
        trade: ProposedTrade,
    ) -> (
        float
        | None
    ):

        if (
            trade.notional_usdt
            is not None
        ):

            return (
                trade.notional_usdt
            )

        if (
            trade.quantity
            is not None
        ):

            return (
                trade.quantity
                *
                trade.entry_price
            )

        return None

    @staticmethod
    def _resolve_position_notional(
        position: OpenPosition,
    ) -> float:

        if (
            position.notional_usdt
            is not None
        ):

            return (
                position.notional_usdt
            )

        price = (
            position.current_price
            or
            position.entry_price
        )

        if (
            position.quantity
            is not None
            and price
            is not None
        ):

            return (
                position.quantity
                *
                price
            )

        return 0.0

    @staticmethod
    def _valid_stop_direction(
        trade: ProposedTrade,
    ) -> bool:

        if (
            trade.stop_loss
            is None
        ):

            return False

        if (
            trade.side
            ==
            TradeBias.LONG
        ):

            return (
                trade.stop_loss
                <
                trade.entry_price
            )

        return (
            trade.stop_loss
            >
            trade.entry_price
        )

    @staticmethod
    def _valid_target_direction(
        trade: ProposedTrade,
    ) -> bool:

        if (
            trade.take_profit
            is None
        ):

            return False

        if (
            trade.side
            ==
            TradeBias.LONG
        ):

            return (
                trade.take_profit
                >
                trade.entry_price
            )

        return (
            trade.take_profit
            <
            trade.entry_price
        )

    @staticmethod
    def _distance_pct(
        entry: float,
        target: (
            float
            | None
        ),
    ) -> (
        float
        | None
    ):

        if target is None:

            return None

        return (
            abs(
                target
                -
                entry
            )
            /
            entry
            *
            100.0
        )

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
                ).lower()
            )

        except (
            ValueError,
            TypeError,
        ):

            return (
                TradeBias.NEUTRAL
            )

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> (
        float
        | None
    ):

        try:

            result = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        return result
