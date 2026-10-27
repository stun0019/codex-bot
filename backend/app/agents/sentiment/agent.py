from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    MarketContext,
    TradeBias,
)

from .models import (
    SentimentInput,
    SentimentOutput,
)


class SentimentAgent(
    BaseAgent[
        SentimentInput,
        SentimentOutput,
    ]
):
    """
    市場情緒分析員。

    未來負責：
    - 社群情緒
    - Funding Rate
    - Open Interest
    - Long / Short Ratio
    - 市場擁擠程度
    - 極端情緒偵測
    """

    name = AgentName.SENTIMENT

    async def analyze(
        self,
        context: MarketContext,
        payload: SentimentInput,
    ) -> SentimentOutput:

        return SentimentOutput(
            agent=self.name,
            status=AgentStatus.SUCCESS,
            symbol=context.symbol,
            bias=TradeBias.NEUTRAL,
            confidence=0.0,
            summary="Sentiment Agent initialized.",
        )
