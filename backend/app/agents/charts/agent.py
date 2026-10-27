from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    MarketContext,
    TradeBias,
)

from .models import (
    ChartsInput,
    ChartsOutput,
)


class ChartsAgent(
    BaseAgent[ChartsInput, ChartsOutput]
):
    """
    圖表與技術分析員。

    不綁定任何特定交易策略。

    未來可分析：
    - Price Action
    - Market Structure
    - Trend
    - Momentum
    - Volatility
    - Volume
    - Support / Resistance
    - Indicators
    - 多時間框架
    - 自訂策略輸出
    """

    name = AgentName.CHARTS

    async def analyze(
        self,
        context: MarketContext,
        payload: ChartsInput,
    ) -> ChartsOutput:

        return ChartsOutput(
            agent=self.name,
            status=AgentStatus.SUCCESS,
            symbol=context.symbol,
            bias=TradeBias.NEUTRAL,
            confidence=0.0,
            summary="Charts Agent initialized.",
            signals=[],
            market_structure={},
            data={
                "timeframes_received": list(
                    payload.candles.keys()
                ),
            },
        )
