from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ..models import (
    AgentOutput,
    TradeBias,
)


class NewsCategory(StrEnum):
    """
    新聞事件分類。

    不綁定特定新聞供應商，
    讓不同來源可以統一轉成相同格式。
    """

    MARKET = "market"
    MACRO = "macro"
    REGULATION = "regulation"
    EXCHANGE = "exchange"
    TOKEN = "token"
    PROTOCOL = "protocol"
    SECURITY = "security"
    ETF = "etf"
    OTHER = "other"


class NewsArticle(BaseModel):
    """
    原始新聞文章。

    News Agent 不負責假設文章來源，
    外部資料來源只要轉成此格式即可。
    """

    title: str

    source: str

    published_at: datetime | None = None

    url: str | None = None

    content: str | None = None

    symbols: list[str] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class NewsInput(BaseModel):
    """
    News Agent 輸入。

    articles:
        待分析新聞。

    focus_symbols:
        優先關注的交易標的。

        例如：

        [
            "BTC-USDT-SWAP",
            "ETH-USDT-SWAP",
        ]

    max_events:
        最多輸出多少個重要事件。
    """

    articles: list[NewsArticle] = Field(
        default_factory=list
    )

    focus_symbols: list[str] = Field(
        default_factory=list
    )

    max_events: int = Field(
        default=10,
        ge=1,
        le=50,
    )


class NewsEvent(BaseModel):
    """
    經 NEWS Agent 分析後的重要新聞事件。

    一個 Event 可以由一篇或多篇新聞形成。

    impact_score:
        事件的重要程度。

        0.0 = 幾乎無影響
        1.0 = 極重大市場事件

    confidence:
        Agent 對事件判斷的信心。

    bias:
        此新聞事件本身對相關市場的方向性。

        LONG
        SHORT
        NEUTRAL

    注意：

    bias 不是交易指令。
    最終交易方向仍由 DECISION Agent 決定。
    """

    title: str

    category: NewsCategory = (
        NewsCategory.OTHER
    )

    affected_symbols: list[str] = Field(
        default_factory=list
    )

    bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    impact_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    description: str = ""

    source_names: list[str] = Field(
        default_factory=list
    )

    source_urls: list[str] = Field(
        default_factory=list
    )

    published_at: datetime | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class NewsOutput(AgentOutput):
    """
    NEWS Agent 最終輸出。

    AgentOutput 已提供：

    agent
    status
    symbol
    bias
    confidence
    summary
    evidence
    data
    errors
    created_at

    NEWS 額外提供：

    events
    """

    events: list[NewsEvent] = Field(
        default_factory=list
    )
