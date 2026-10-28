from __future__ import annotations

import asyncio

from typing import (
    Awaitable,
)

from fastapi import (
    APIRouter,
)

from ..agents.charts.models import (
    ChartsOutput,
)

from ..agents.charts.service import (
    ChartsService,
)

from ..agents.models import (
    AgentName,
)

from ..agents.news.models import (
    NewsOutput,
)

from ..agents.news.service import (
    NewsService,
)

from ..agents.risk.service import (
    RiskService,
)

from ..agents.scout.agent import (
    ScoutAgent,
)

from ..agents.scout.models import (
    ScoutOutput,
)

from ..agents.sentiment.models import (
    SentimentOutput,
)

from ..agents.sentiment.service import (
    SentimentService,
)

from .models import (
    ChartsApiRequest,
    NewsApiRequest,
    RiskApiRequest,
    RiskApiResponse,
    ScoutApiRequest,
    SentimentApiRequest,
)


router = APIRouter(
    prefix="/api",
    tags=[
        "codex",
    ],
)


# =====================================
# HEALTH
# =====================================


@router.get(
    "/health"
)
async def health(
) -> dict[
    str,
    object,
]:

    return {
        "status":
            "ok",

        "service":
            "codex-bot",

        "api_version":
            "1",

        "agents_ready":
            6,

        "agents_total":
            6,
    }


# =====================================
# AGENT CATALOG
# =====================================


@router.get(
    "/agents"
)
async def agents(
) -> dict[
    str,
    object,
]:

    return {
        "ready":
            6,

        "total":
            6,

        "agents": [
            {
                "name":
                    AgentName.SCOUT.value,

                "status":
                    "ready",

                "endpoint":
                    "/api/scout",
            },

            {
                "name":
                    AgentName.NEWS.value,

                "status":
                    "v1_ready",

                "endpoint":
                    "/api/news",
            },

            {
                "name":
                    AgentName.SENTIMENT.value,

                "status":
                    "v1_ready",

                "endpoint":
                    "/api/sentiment",
            },

            {
                "name":
                    AgentName.CHARTS.value,

                "status":
                    "v1_ready",

                "endpoint":
                    "/api/charts",
            },

            {
                "name":
                    AgentName.RISK.value,

                "status":
                    "v1_ready",

                "endpoint":
                    "/api/risk",
            },

            {
                "name":
                    AgentName.DECISION.value,

                "status":
                    "v1_ready",

                "endpoint":
                    "/api/decision",
            },
        ],
    }


# =====================================
# SCOUT
# =====================================


@router.post(
    "/scout",
    response_model=ScoutOutput,
)
async def scout(
    request: ScoutApiRequest,
) -> ScoutOutput:

    agent = ScoutAgent()

    return (
        await agent.analyze(
            context=(
                request.context
            ),

            payload=(
                request.payload
            ),
        )
    )


# =====================================
# NEWS
# =====================================


@router.post(
    "/news",
    response_model=NewsOutput,
)
async def news(
    request: NewsApiRequest,
) -> NewsOutput:

    async with (
        NewsService()
        as service
    ):

        return (
            await service.analyze(
                context=(
                    request.context
                ),

                focus_symbols=(
                    request.focus_symbols
                    or None
                ),
            )
        )


# =====================================
# SENTIMENT
# =====================================


@router.post(
    "/sentiment",
    response_model=SentimentOutput,
)
async def sentiment(
    request: SentimentApiRequest,
) -> SentimentOutput:

    async with (
        SentimentService()
        as service
    ):

        return (
            await service.analyze(
                context=(
                    request.context
                )
            )
        )


# =====================================
# CHARTS
# =====================================


@router.post(
    "/charts",
    response_model=ChartsOutput,
)
async def charts(
    request: ChartsApiRequest,
) -> ChartsOutput:

    async with (
        ChartsService()
        as service
    ):

        return (
            await service.analyze(
                context=(
                    request.context
                )
            )
        )


# =====================================
# RISK ENRICHMENT
# =====================================


async def _run_charts(
    request: RiskApiRequest,
) -> ChartsOutput:

    async with (
        ChartsService()
        as service
    ):

        return (
            await service.analyze(
                context=(
                    request.context
                )
            )
        )


async def _run_sentiment(
    request: RiskApiRequest,
) -> SentimentOutput:

    async with (
        SentimentService()
        as service
    ):

        return (
            await service.analyze(
                context=(
                    request.context
                )
            )
        )


async def _run_news(
    request: RiskApiRequest,
) -> NewsOutput:

    async with (
        NewsService()
        as service
    ):

        return (
            await service.analyze(
                context=(
                    request.context
                ),

                focus_symbols=[
                    request
                    .context
                    .symbol
                ],
            )
        )


# =====================================
# RISK
# =====================================


@router.post(
    "/risk",
    response_model=RiskApiResponse,
)
async def risk(
    request: RiskApiRequest,
) -> RiskApiResponse:

    charts_output: (
        ChartsOutput
        | None
    ) = None

    sentiment_output: (
        SentimentOutput
        | None
    ) = None

    news_output: (
        NewsOutput
        | None
    ) = None

    enrichment_errors: list[
        str
    ] = []

    # =================================
    # OPTIONAL ENRICHMENT
    # =================================

    if request.enrich:

        jobs: list[
            tuple[
                str,
                Awaitable[
                    ChartsOutput
                    |
                    SentimentOutput
                    |
                    NewsOutput
                ],
            ]
        ] = []

        if (
            not request
            .payload
            .charts_result
        ):

            jobs.append(
                (
                    "charts",
                    _run_charts(
                        request
                    ),
                )
            )

        if (
            not request
            .payload
            .sentiment_result
        ):

            jobs.append(
                (
                    "sentiment",
                    _run_sentiment(
                        request
                    ),
                )
            )

        if (
            request.include_news
            and
            not request
            .payload
            .news_result
        ):

            jobs.append(
                (
                    "news",
                    _run_news(
                        request
                    ),
                )
            )

        if jobs:

            results = (
                await asyncio.gather(
                    *[
                        job
                        for _, job
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

                    enrichment_errors.append(
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
                    "charts"
                ):

                    charts_output = (
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
                    "news"
                ):

                    news_output = (
                        result
                    )

    # =================================
    # RISK ANALYSIS
    # =================================

    service = RiskService()

    risk_output = (
        await service.analyze(
            context=(
                request.context
            ),

            payload=(
                request.payload
            ),

            charts_result=(
                charts_output
            ),

            sentiment_result=(
                sentiment_output
            ),

            news_result=(
                news_output
            ),
        )
    )

    # =================================
    # DIAGNOSTICS
    # =================================

    data = dict(
        risk_output.data
    )

    data[
        "api_enrichment"
    ] = {
        "requested":
            request.enrich,

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
                        request
                        .payload
                        .charts_result
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
                        request
                        .payload
                        .sentiment_result
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
                        request
                        .payload
                        .news_result
                    )

                    else
                    "not_run"
                )
            ),

        "errors":
            enrichment_errors,
    }

    risk_output = (
        risk_output.model_copy(
            update={
                "data":
                    data,
            },

            deep=True,
        )
    )

    return RiskApiResponse(
        risk=risk_output,

        charts=(
            charts_output
        ),

        sentiment=(
            sentiment_output
        ),

        news=(
            news_output
        ),

        enrichment_errors=(
            enrichment_errors
        ),
    )
