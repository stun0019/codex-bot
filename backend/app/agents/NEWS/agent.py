from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    MarketContext,
    TradeBias,
)

from .models import (
    NewsInput,
    NewsOutput,
)


class NewsAgent(
    BaseAgent[NewsInput, NewsOutput]
):
    """
    新聞分析員。

    未來負責：
    - 加密貨幣新聞
    - 宏觀經濟事件
    - 監管消息
    - 交易所公告
    - Token / protocol 重大事件
    """

    name = AgentName.NEWS

    async def analyze(
        self,
        context: MarketContext,
        payload: NewsInput,
    ) -> NewsOutput:

        return NewsOutput(
            agent=self.name,
            status=AgentStatus.SUCCESS,
            symbol=context.symbol,
            bias=TradeBias.NEUTRAL,
            confidence=0.0,
            summary="News Agent initialized.",
            events=[],
            data={
                "articles_received": len(
                    payload.articles
                ),
            },
        )
