from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)

from ..agents.charts.models import (
    ChartsOutput,
)

from ..agents.models import (
    MarketContext,
)

from ..agents.news.models import (
    NewsOutput,
)

from ..agents.risk.models import (
    RiskInput,
    RiskOutput,
)

from ..agents.scout.models import (
    ScoutInput,
)

from ..agents.sentiment.models import (
    SentimentOutput,
)


class ScoutApiRequest(
    BaseModel
):
    context: MarketContext = Field(
        default_factory=lambda:
            MarketContext(
                symbol="MARKET",
            )
    )

    payload: ScoutInput = Field(
        default_factory=ScoutInput
    )


class NewsApiRequest(
    BaseModel
):
    context: MarketContext

    focus_symbols: list[
        str
    ] = Field(
        default_factory=list
    )


class SentimentApiRequest(
    BaseModel
):
    context: MarketContext


class ChartsApiRequest(
    BaseModel
):
    context: MarketContext


class RiskApiRequest(
    BaseModel
):
    """
    enrich=True:

        如果 payload 沒有附：
        - charts_result
        - sentiment_result

        API 會先自動執行對應 Agent。

    include_news=False:

        預設不自動執行 NEWS，
        避免每一次 RISK 都產生
        RSS + optional LLM 成本。

        需要時明確打開即可。
    """

    context: MarketContext

    payload: RiskInput

    enrich: bool = True

    include_news: bool = False


class RiskApiResponse(
    BaseModel
):
    risk: RiskOutput

    charts: (
        ChartsOutput
        | None
    ) = None

    sentiment: (
        SentimentOutput
        | None
    ) = None

    news: (
        NewsOutput
        | None
    ) = None

    enrichment_errors: list[
        str
    ] = Field(
        default_factory=list
    )
