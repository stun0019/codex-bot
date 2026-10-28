from __future__ import annotations

import asyncio

from typing import Any

from fastapi import (
    APIRouter,
)

from pydantic import (
    BaseModel,
    Field,
)

from ..agents.charts.models import (
    ChartsOutput,
)

from ..agents.charts.service import (
    ChartsService,
)

from ..agents.decision import (
    DecisionInput,
    DecisionOutput,
    DecisionService,
)

from ..agents.models import (
    MarketContext,
)

from ..agents.news.models import (
    NewsOutput,
)

from ..agents.news.service import (
    NewsService,
)

from ..agents.risk.models import (
    RiskInput,
    RiskOutput,
)

from ..agents.risk.service import (
    RiskService,
)

from ..agents.scout.agent import (
    ScoutAgent,
)

from ..agents.scout.models import (
    ScoutInput,
    ScoutOutput,
)

from ..agents.sentiment.models import (
    SentimentOutput,
)

from ..agents.sentiment.service import (
    SentimentService,
)


router = APIRouter(
    prefix="/api",
    tags=[
        "decision",
    ],
)


# =====================================
# API Models
# =====================================


class DecisionApiRequest(
    BaseModel
):
    """
    DECISION API request.

    payload:
        可以直接提供既有：

        - scout_result
        - news_result
        - sentiment_result
        - charts_result
        - risk_result
        - proposed_trade

    risk_payload:
        如果希望 API 自動執行 RISK，
        可以提供 RiskInput。

    enrich:
        True 時，自動補齊缺少的：

        - SCOUT
        - NEWS
        - SENTIMENT
        - CHARTS

    include_scout:
        是否自動執行 SCOUT。

    include_news:
        是否自動執行 NEWS。
    """

    context: MarketContext

    payload: DecisionInput = Field(
        default_factory=DecisionInput
    )

    risk_payload: (
        RiskInput
        | None
    ) = None

    enrich: bool = True

    include_scout: bool = True

    include_news: bool = True


class DecisionApiResponse(
    BaseModel
):
    decision: DecisionOutput

    scout: (
        ScoutOutput
        | None
    ) = None

    news: (
        NewsOutput
        | None
    ) = None

    sentiment: (
        SentimentOutput
        | None
    ) = None

    charts: (
        ChartsOutput
        | None
    ) = None

    risk: (
        RiskOutput
        | None
    ) = None

    pipeline_errors: list[
        str
    ] = Field(
        default_factory=list
    )


# =====================================
# Pipeline Helpers
# =====================================


async def _run_scout(
    context: MarketContext,
) -> ScoutOutput:
    """
    Run SCOUT.

    SCOUT 是市場機會品質判斷，
    不直接決定 LONG / SHORT。
    """

    agent = ScoutAgent()

    return (
        await agent.analyze(
            context=context,

            payload=(
                ScoutInput(
                    symbols=[]
                )
            ),
        )
    )


async def _run_news(
    context: MarketContext,
) -> NewsOutput:
    """
    Run NEWS for the current symbol.
    """

    async with (
        NewsService()
        as service
    ):

        return (
            await service.analyze(
                context=context,

                focus_symbols=[
                    context.symbol
                ],
            )
        )


async def _run_sentiment(
    context: MarketContext,
) -> SentimentOutput:
    """
    Run SENTIMENT.
    """

    async with (
        SentimentService()
        as service
    ):

        return (
            await service.analyze(
                context=context
            )
        )


async def _run_charts(
    context: MarketContext,
) -> ChartsOutput:
    """
    Run CHARTS.
    """

    async with (
        ChartsService()
        as service
    ):

        return (
            await service.analyze(
                context=context
            )
        )


def _parse_optional(
    model_type,
    value: dict[
        str,
        Any,
    ],
):
    """
    Try to restore a serialized AgentOutput
    into its concrete Pydantic model.

    Invalid / incomplete dicts return None,
    so DECISION can continue using enrichment.
    """

    if not value:

        return None

    try:

        return (
            model_type.model_validate(
                value
            )
        )

    except Exception:

        return None


# =====================================
# DECISION
# =====================================


@router.post(
    "/decision",
    response_model=(
        DecisionApiResponse
    ),
)
async def decision(
    request: DecisionApiRequest,
) -> DecisionApiResponse:
    """
    Full multi-agent decision pipeline.

    Flow:

        SCOUT
        NEWS
        SENTIMENT
        CHARTS
            ↓
          RISK
            ↓
        DECISION
            ↓
        LONG / SHORT / WAIT

    注意：

    DECISION 不直接向交易所下單。
    """

    payload = (
        request.payload
    )

    context = (
        request.context
    )

    pipeline_errors: list[
        str
    ] = []

    # =================================
    # Restore already supplied results
    # =================================

    scout_output = (
        _parse_optional(
            ScoutOutput,
            payload.scout_result,
        )
    )

    news_output = (
        _parse_optional(
            NewsOutput,
            payload.news_result,
        )
    )

    sentiment_output = (
        _parse_optional(
            SentimentOutput,
            payload.sentiment_result,
        )
    )

    charts_output = (
        _parse_optional(
            ChartsOutput,
            payload.charts_result,
        )
    )

    risk_output = (
        _parse_optional(
            RiskOutput,
            payload.risk_result,
        )
    )

    # =================================
    # Optional enrichment
    # =================================

    if request.enrich:

        jobs: list[
            tuple[
                str,
                Any,
            ]
        ] = []

        # SCOUT
        if (
            request.include_scout
            and
            not payload.scout_result
        ):

            jobs.append(
                (
                    "scout",
                    _run_scout(
                        context
                    ),
                )
            )

        # NEWS
        if (
            request.include_news
            and
            not payload.news_result
        ):

            jobs.append(
                (
                    "news",
                    _run_news(
                        context
                    ),
                )
            )

        # SENTIMENT
        if (
            not payload
            .sentiment_result
        ):

            jobs.append(
                (
                    "sentiment",
                    _run_sentiment(
                        context
                    ),
                )
            )

        # CHARTS
        if (
            not payload
            .charts_result
        ):

            jobs.append(
                (
                    "charts",
                    _run_charts(
                        context
                    ),
                )
            )

        # Run market agents concurrently
        if jobs:

            results = (
                await asyncio.gather(
                    *[
                        coroutine
                        for _, coroutine
                        in jobs
                    ],

                    return_exceptions=True,
                )
            )

            for (
                (
                    name,
                    _,
                ),
                result,
            ) in zip(
                jobs,
                results,
                strict=True,
            ):

                if isinstance(
                    result,
                    BaseException,
                ):

                    pipeline_errors.append(
                        (
                            f"{name}: "
                            f"{type(result).__name__}: "
                            f"{result}"
                        )
                    )

                    continue

                if (
                    name
                    ==
                    "scout"
                ):

                    scout_output = (
                        result
                    )

                elif (
                    name
                    ==
                    "news"
                ):

                    news_output = (
                        result
                    )

                elif (
                    name
                    ==
                    "sentiment"
                ):

                    sentiment_output = (
                        result
                    )

                elif (
                    name
                    ==
                    "charts"
                ):

                    charts_output = (
                        result
                    )

    # =================================
    # Proposed Trade
    # =================================

    proposed_trade = (
        payload.proposed_trade
    )

    if (
        proposed_trade is None
        and
        request.risk_payload
        is not None
    ):

        proposed_trade = (
            request
            .risk_payload
            .proposed_trade
        )

    # =================================
    # RISK
    # =================================
    #
    # 如果 request 已提供 risk_result，
    # 使用既有結果。
    #
    # 否則如果有 risk_payload，
    # 自動跑 RISK。
    #
    # RISK 會接：
    #
    # CHARTS
    # SENTIMENT
    # NEWS
    #
    # 作為風險證據。
    # =================================

    if (
        risk_output is None
        and
        request.risk_payload
        is not None
    ):

        try:

            risk_service = (
                RiskService()
            )

            risk_output = (
                await risk_service.analyze(
                    context=context,

                    payload=(
                        request
                        .risk_payload
                    ),

                    charts_result=(
                        charts_output
                        if (
                            charts_output
                            is not None
                        )
                        else (
                            payload
                            .charts_result
                            or None
                        )
                    ),

                    sentiment_result=(
                        sentiment_output
                        if (
                            sentiment_output
                            is not None
                        )
                        else (
                            payload
                            .sentiment_result
                            or None
                        )
                    ),

                    news_result=(
                        news_output
                        if (
                            news_output
                            is not None
                        )
                        else (
                            payload
                            .news_result
                            or None
                        )
                    ),
                )
            )

        except Exception as exc:

            pipeline_errors.append(
                (
                    "risk: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
            )

    # =================================
    # DECISION
    # =================================

    decision_service = (
        DecisionService()
    )

    decision_output = (
        await decision_service.analyze(
            context=context,

            payload=payload,

            scout_result=(
                scout_output
                if (
                    scout_output
                    is not None
                )
                else None
            ),

            news_result=(
                news_output
                if (
                    news_output
                    is not None
                )
                else None
            ),

            sentiment_result=(
                sentiment_output
                if (
                    sentiment_output
                    is not None
                )
                else None
            ),

            charts_result=(
                charts_output
                if (
                    charts_output
                    is not None
                )
                else None
            ),

            risk_result=(
                risk_output
                if (
                    risk_output
                    is not None
                )
                else None
            ),

            proposed_trade=(
                proposed_trade
            ),
        )
    )

    # =================================
    # API Pipeline Diagnostics
    # =================================

    decision_data = dict(
        decision_output.data
    )

    decision_data[
        "pipeline_errors"
    ] = (
        pipeline_errors
    )

    decision_data[
        "pipeline"
    ] = {

        "scout":
            (
                scout_output
                .status
                .value

                if (
                    scout_output
                    is not None
                )

                else (
                    "provided"

                    if (
                        payload.scout_result
                    )

                    else
                    "not_run"
                )
            ),

        "news":
            (
                news_output
                .status
                .value

                if (
                    news_output
                    is not None
                )

                else (
                    "provided"

                    if (
                        payload.news_result
                    )

                    else
                    "not_run"
                )
            ),

        "sentiment":
            (
                sentiment_output
                .status
                .value

                if (
                    sentiment_output
                    is not None
                )

                else (
                    "provided"

                    if (
                        payload
                        .sentiment_result
                    )

                    else
                    "not_run"
                )
            ),

        "charts":
            (
                charts_output
                .status
                .value

                if (
                    charts_output
                    is not None
                )

                else (
                    "provided"

                    if (
                        payload.charts_result
                    )

                    else
                    "not_run"
                )
            ),

        "risk":
            (
                risk_output
                .status
                .value

                if (
                    risk_output
                    is not None
                )

                else (
                    "provided"

                    if (
                        payload.risk_result
                    )

                    else
                    "not_run"
                )
            ),
    }

    decision_output = (
        decision_output.model_copy(
            update={
                "data":
                    decision_data,
            },

            deep=True,
        )
    )

    # =================================
    # Response
    # =================================

    return DecisionApiResponse(
        decision=(
            decision_output
        ),

        scout=(
            scout_output
        ),

        news=(
            news_output
        ),

        sentiment=(
            sentiment_output
        ),

        charts=(
            charts_output
        ),

        risk=(
            risk_output
        ),

        pipeline_errors=(
            pipeline_errors
        ),
    )
