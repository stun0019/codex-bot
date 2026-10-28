from __future__ import annotations

import asyncio

from ..agents.charts import (
    ChartsOutput,
    ChartsService,
    TradePlan,
    TradePlanBuilder,
)

from ..agents.decision import (
    DecisionService,
)

from ..agents.models import (
    AgentStatus,
    MarketContext,
    TradeBias,
)

from ..agents.news.models import (
    NewsOutput,
)

from ..agents.news.service import (
    NewsService,
)

from ..agents.risk.models import (
    ProposedTrade,
    RiskInput,
)

from ..agents.risk.service import (
    RiskService,
)

from ..agents.scout.agent import (
    ScoutAgent,
)

from ..agents.scout.models import (
    ScoutCandidate,
    ScoutInput,
    ScoutOutput,
)

from ..agents.scout.scanner import (
    ScoutScanConfig,
    ScoutScanner,
)

from ..agents.sentiment.models import (
    SentimentOutput,
)

from ..agents.sentiment.service import (
    SentimentService,
)

from .models import (
    OpportunitiesOutput,
    OpportunityResult,
    OpportunityScanInput,
    OpportunityStatus,
)


class OpportunitiesService:
    """
    RUN ALL orchestration。

    Flow:

        SCOUT
          ↓
        Top candidates
          ↓
        NEWS
        SENTIMENT
        CHARTS
          ↓
        CHARTS TradePlan
          ↓
        deterministic proposed size
          ↓
        RISK
          ↓
        DECISION
          ↓
        actionable opportunities

    這不是新 Agent。

    它只是把既有六個 Agent
    串成一條完整 workflow。
    """

    def __init__(
        self,
        trade_plan_builder: (
            TradePlanBuilder
            | None
        ) = None,
    ) -> None:

        self.trade_plan_builder = (
            trade_plan_builder
            if trade_plan_builder
            is not None
            else TradePlanBuilder()
        )

    async def scan(
        self,
        payload: OpportunityScanInput,
    ) -> OpportunitiesOutput:

        errors: list[str] = []

        scout = (
            await self._run_scout(
                payload
            )
        )

        if (
            scout.status
            !=
            AgentStatus.SUCCESS
        ):

            return OpportunitiesOutput(
                status="error",

                errors=[
                    "SCOUT failed.",
                    *scout.errors,
                ],
            )

        candidates = [
            candidate
            for candidate
            in scout.candidates
            if (
                candidate.score
                >=
                payload.minimum_scout_score
            )
        ][
            :payload.max_candidates
        ]

        semaphore = (
            asyncio.Semaphore(
                payload.max_concurrency
            )
        )

        async def evaluate(
            candidate: ScoutCandidate,
        ) -> OpportunityResult:

            async with semaphore:

                return (
                    await self._evaluate_candidate(
                        candidate=candidate,
                        scout=scout,
                        payload=payload,
                    )
                )

        results = (
            await asyncio.gather(
                *[
                    evaluate(
                        candidate
                    )
                    for candidate
                    in candidates
                ],

                return_exceptions=True,
            )
        )

        evaluated: list[
            OpportunityResult
        ] = []

        for (
            candidate,
            result,
        ) in zip(
            candidates,
            results,
            strict=True,
        ):

            if isinstance(
                result,
                BaseException,
            ):

                message = (
                    f"{candidate.symbol}: "
                    f"{type(result).__name__}: "
                    f"{result}"
                )

                errors.append(
                    message
                )

                evaluated.append(
                    OpportunityResult(
                        symbol=(
                            candidate.symbol
                        ),

                        status=(
                            OpportunityStatus.ERROR
                        ),

                        scout_score=(
                            candidate.score
                        ),

                        errors=[
                            message
                        ],
                    )
                )

                continue

            evaluated.append(
                result
            )

        opportunities = [
            item
            for item
            in evaluated
            if (
                item.status
                ==
                OpportunityStatus.ACTIONABLE
            )
        ]

        opportunities.sort(
            key=lambda item:
                item.rank_score,
            reverse=True,
        )

        return OpportunitiesOutput(
            status="success",

            scanned_count=(
                len(
                    scout.candidates
                )
            ),

            evaluated_count=(
                len(
                    evaluated
                )
            ),

            actionable_count=(
                len(
                    opportunities
                )
            ),

            opportunities=(
                opportunities
            ),

            evaluated=(
                evaluated
            ),

            errors=errors,
        )

    async def _run_scout(
        self,
        payload: OpportunityScanInput,
    ) -> ScoutOutput:

        config = ScoutScanConfig(
            top_n=(
                payload.max_candidates
            ),

            detail_pool_size=max(
                20,
                payload.max_candidates
                *
                4,
            ),
        )

        async with ScoutScanner(
            config=config
        ) as scanner:

            agent = ScoutAgent(
                scanner=scanner
            )

            return (
                await agent.analyze(
                    context=(
                        MarketContext(
                            symbol="MARKET",

                            exchange="OKX",

                            market_type="swap",
                        )
                    ),

                    payload=(
                        ScoutInput(
                            symbols=[]
                        )
                    ),
                )
            )

    async def _evaluate_candidate(
        self,
        *,
        candidate: ScoutCandidate,
        scout: ScoutOutput,
        payload: OpportunityScanInput,
    ) -> OpportunityResult:

        symbol = (
            candidate.symbol
            .strip()
            .upper()
        )

        context = MarketContext(
            symbol=symbol,

            exchange="OKX",

            market_type="swap",

            timeframes=[
                "15m",
                "1H",
                "4H",
            ],
        )

        charts_task = (
            self._run_charts(
                context
            )
        )

        sentiment_task = (
            self._run_sentiment(
                context
            )
        )

        tasks = [
            charts_task,
            sentiment_task,
        ]

        if payload.include_news:

            tasks.append(
                self._run_news(
                    context
                )
            )

        outputs = (
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )
        )

        charts = (
            outputs[0]
        )

        sentiment = (
            outputs[1]
        )

        news = (
            outputs[2]
            if (
                payload.include_news
                and
                len(outputs) >= 3
            )
            else None
        )

        errors: list[str] = []

        if isinstance(
            charts,
            BaseException,
        ):

            errors.append(
                (
                    "CHARTS: "
                    f"{type(charts).__name__}: "
                    f"{charts}"
                )
            )

            charts = None

        if isinstance(
            sentiment,
            BaseException,
        ):

            errors.append(
                (
                    "SENTIMENT: "
                    f"{type(sentiment).__name__}: "
                    f"{sentiment}"
                )
            )

            sentiment = None

        if isinstance(
            news,
            BaseException,
        ):

            errors.append(
                (
                    "NEWS: "
                    f"{type(news).__name__}: "
                    f"{news}"
                )
            )

            news = None

        if (
            charts is None
            or
            charts.status
            !=
            AgentStatus.SUCCESS
        ):

            return OpportunityResult(
                symbol=symbol,

                status=(
                    OpportunityStatus.WAIT
                ),

                scout_score=(
                    candidate.score
                ),

                reasons=[
                    (
                        "CHARTS did not produce "
                        "usable technical analysis."
                    )
                ],

                errors=errors,
            )

        trade_plan = (
            self.trade_plan_builder
            .build(
                charts
            )
        )

        if trade_plan is None:

            return OpportunityResult(
                symbol=symbol,

                status=(
                    OpportunityStatus.WAIT
                ),

                scout_score=(
                    candidate.score
                ),

                directional_bias=(
                    charts.bias
                ),

                confidence=(
                    charts.confidence
                ),

                reasons=[
                    (
                        "No actionable CHARTS "
                        "trade plan."
                    ),

                    (
                        "Possible causes: "
                        "4H/1H misalignment, "
                        "15m not confirmed, "
                        "low confidence, or "
                        "insufficient R:R."
                    ),
                ],

                errors=errors,
            )

        notional = (
            self._recommended_initial_notional(
                trade_plan=(
                    trade_plan
                ),

                payload=payload,
            )
        )

        if (
            notional is None
            or
            notional <= 0
        ):

            return OpportunityResult(
                symbol=symbol,

                status=(
                    OpportunityStatus.WAIT
                ),

                scout_score=(
                    candidate.score
                ),

                directional_bias=(
                    trade_plan.side
                ),

                trade_plan=(
                    trade_plan
                ),

                reasons=[
                    (
                        "No available risk capacity "
                        "for this trade."
                    )
                ],

                errors=errors,
            )

        proposed_trade = ProposedTrade(
            symbol=symbol,

            side=(
                trade_plan.side
            ),

            entry_price=(
                trade_plan.entry_price
            ),

            current_price=(
                trade_plan.entry_price
            ),

            stop_loss=(
                trade_plan.stop_loss
            ),

            take_profit=(
                trade_plan.take_profit
            ),

            leverage=(
                payload.leverage
            ),

            notional_usdt=(
                notional
            ),

            strategy=(
                trade_plan.setup_type
            ),

            metadata={
                "trade_plan_confidence":
                    trade_plan.confidence,

                "entry_timeframe":
                    trade_plan.entry_timeframe,

                "risk_reward_ratio":
                    trade_plan
                    .risk_reward_ratio,
            },
        )

        risk_input = RiskInput(
            account_equity=(
                payload.account_equity
            ),

            available_balance=(
                payload.available_balance
            ),

            daily_pnl=(
                payload.daily_pnl
            ),

            open_positions=(
                payload.open_positions
            ),

            proposed_trade=(
                proposed_trade
            ),

            risk_limits=(
                payload.risk_limits
            ),
        )

        risk_service = (
            RiskService()
        )

        risk = (
            await risk_service.analyze(
                context=context,

                payload=risk_input,

                charts_result=charts,

                sentiment_result=(
                    sentiment
                    if (
                        isinstance(
                            sentiment,
                            SentimentOutput,
                        )
                    )
                    else None
                ),

                news_result=(
                    news
                    if (
                        isinstance(
                            news,
                            NewsOutput,
                        )
                    )
                    else None
                ),
            )
        )

        decision_service = (
            DecisionService()
        )

        decision = (
            await decision_service.analyze(
                context=context,

                scout_result=scout,

                charts_result=charts,

                sentiment_result=(
                    sentiment
                    if (
                        isinstance(
                            sentiment,
                            SentimentOutput,
                        )
                    )
                    else None
                ),

                news_result=(
                    news
                    if (
                        isinstance(
                            news,
                            NewsOutput,
                        )
                    )
                    else None
                ),

                risk_result=risk,

                proposed_trade=(
                    proposed_trade
                ),

                require_risk_approval=True,
            )
        )

        actionable = (
            decision.status
            ==
            AgentStatus.SUCCESS
            and
            decision.bias
            in (
                TradeBias.LONG,
                TradeBias.SHORT,
            )
            and
            risk.approved
        )

        rank_score = (
            self._rank_score(
                scout_score=(
                    candidate.score
                ),

                charts_confidence=(
                    charts.confidence
                ),

                plan_confidence=(
                    trade_plan.confidence
                ),

                risk_confidence=(
                    risk.confidence
                ),

                decision_confidence=(
                    decision.confidence
                ),
            )
        )

        reasons = list(
            decision
            .decision
            .reasoning
        )

        if not actionable:

            reasons.insert(
                0,
                (
                    "Candidate did not pass "
                    "all final decision gates."
                )
            )

        return OpportunityResult(
            symbol=symbol,

            status=(
                OpportunityStatus.ACTIONABLE
                if actionable
                else OpportunityStatus.WAIT
            ),

            scout_score=(
                candidate.score
            ),

            action=(
                decision.bias
            ),

            directional_bias=(
                decision
                .directional_bias
            ),

            confidence=(
                decision.confidence
            ),

            rank_score=(
                rank_score
            ),

            trade_plan=(
                trade_plan
            ),

            risk_verdict=(
                risk.verdict.value
            ),

            risk_approved=(
                risk.approved
            ),

            recommended_notional_usdt=(
                risk
                .metrics
                .recommended_notional_usdt
                or
                notional
            ),

            estimated_loss_usdt=(
                risk
                .metrics
                .estimated_loss_usdt
            ),

            risk_pct_equity=(
                risk
                .metrics
                .risk_pct_equity
            ),

            reasons=reasons,

            errors=[
                *errors,
                *risk.errors,
                *decision.errors,
            ],
        )

    async def _run_charts(
        self,
        context: MarketContext,
    ) -> ChartsOutput:

        async with ChartsService() as service:

            return (
                await service.analyze(
                    context=context
                )
            )

    async def _run_sentiment(
        self,
        context: MarketContext,
    ) -> SentimentOutput:

        async with SentimentService() as service:

            return (
                await service.analyze(
                    context=context
                )
            )

    async def _run_news(
        self,
        context: MarketContext,
    ) -> NewsOutput:

        async with NewsService() as service:

            return (
                await service.analyze(
                    context=context,

                    focus_symbols=[
                        context.symbol
                    ],
                )
            )

    @staticmethod
    def _recommended_initial_notional(
        *,
        trade_plan: TradePlan,
        payload: OpportunityScanInput,
    ) -> float | None:

        equity = (
            payload.account_equity
        )

        available = (
            payload.available_balance
        )

        limits = (
            payload.risk_limits
        )

        risk_fraction = (
            trade_plan
            .risk_distance_pct
            /
            100.0
        )

        if risk_fraction <= 0:

            return None

        # Risk-budget based size.

        risk_budget = (
            equity
            *
            limits.max_risk_per_trade_pct
            /
            100.0
        )

        by_risk = (
            risk_budget
            /
            risk_fraction
        )

        # Single-position cap.

        by_position = (
            equity
            *
            limits
            .max_position_notional_pct
            /
            100.0
        )

        # Keep configured free balance reserve.

        free_reserve = (
            equity
            *
            limits.min_free_balance_pct
            /
            100.0
        )

        deployable_margin = max(
            0.0,
            available
            -
            free_reserve,
        )

        by_margin = (
            deployable_margin
            *
            payload.leverage
        )

        existing_total = sum(
            OpportunitiesService
            ._position_notional(
                position
            )

            for position
            in payload.open_positions
        )

        existing_symbol = sum(
            OpportunitiesService
            ._position_notional(
                position
            )

            for position
            in payload.open_positions

            if (
                position.symbol
                .strip()
                .upper()
                ==
                trade_plan.symbol
                .strip()
                .upper()
            )
        )

        max_total = (
            equity
            *
            limits.max_total_exposure_pct
            /
            100.0
        )

        max_symbol = (
            equity
            *
            limits.max_symbol_exposure_pct
            /
            100.0
        )

        remaining_total = max(
            0.0,
            max_total
            -
            existing_total,
        )

        remaining_symbol = max(
            0.0,
            max_symbol
            -
            existing_symbol,
        )

        candidates = [
            by_risk,
            by_position,
            by_margin,
            remaining_total,
            remaining_symbol,
        ]

        positive = [
            value
            for value
            in candidates
            if (
                value is not None
                and
                value > 0
            )
        ]

        if not positive:

            return None

        result = min(
            positive
        )

        if result <= 0:

            return None

        return result

    @staticmethod
    def _position_notional(
        position,
    ) -> float:

        if (
            position.notional_usdt
            is not None
        ):

            return max(
                0.0,
                position.notional_usdt,
            )

        if (
            position.quantity
            is not None
            and
            position.current_price
            is not None
        ):

            return max(
                0.0,
                position.quantity
                *
                position.current_price,
            )

        if (
            position.quantity
            is not None
            and
            position.entry_price
            is not None
        ):

            return max(
                0.0,
                position.quantity
                *
                position.entry_price,
            )

        return 0.0

    @staticmethod
    def _rank_score(
        *,
        scout_score: float,
        charts_confidence: float,
        plan_confidence: float,
        risk_confidence: float,
        decision_confidence: float,
    ) -> float:

        score = (
            scout_score
            *
            0.15
            +
            charts_confidence
            *
            0.15
            +
            plan_confidence
            *
            0.20
            +
            risk_confidence
            *
            0.15
            +
            decision_confidence
            *
            0.35
        )

        return max(
            0.0,
            min(
                1.0,
                score,
            ),
        )
