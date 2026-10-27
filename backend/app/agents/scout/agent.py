from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    MarketContext,
    TradeBias,
)

from .models import (
    ScoutInput,
    ScoutOutput,
)


class ScoutAgent(
    BaseAgent[ScoutInput, ScoutOutput]
):
    """
    市場機會掃描員。

    未來負責：
    - 成交量異常
    - 波動率
    - 流動性
    - 價格異動
    - 市場活躍度
    - 候選交易標的排名
    """

    name = AgentName.SCOUT

    async def analyze(
        self,
        context: MarketContext,
        payload: ScoutInput,
    ) -> ScoutOutput:

        return ScoutOutput(
            agent=self.name,
            status=AgentStatus.SUCCESS,
            symbol=context.symbol,
            bias=TradeBias.NEUTRAL,
            confidence=0.0,
            summary="Scout Agent initialized.",
            candidates=[],
            data={
                "symbols_received": payload.symbols,
            },
        )
