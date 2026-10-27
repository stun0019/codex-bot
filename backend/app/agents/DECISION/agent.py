from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    MarketContext,
    TradeBias,
)

from .models import (
    DecisionInput,
    DecisionOutput,
    TradeDecision,
)


class DecisionAgent(
    BaseAgent[
        DecisionInput,
        DecisionOutput,
    ]
):
    """
    最終決策 Agent。

    未來負責整合：

    - Scout
    - News
    - Sentiment
    - Charts
    - Risk

    最終輸出：
    - LONG
    - SHORT
    - WAIT

    Decision Agent 本身不直接向交易所下單。
    """

    name = AgentName.DECISION

    async def analyze(
        self,
        context: MarketContext,
        payload: DecisionInput,
    ) -> DecisionOutput:

        decision = TradeDecision(
            action=TradeBias.WAIT,
            symbol=context.symbol,
            reasoning=[
                "Decision logic has not been implemented yet."
            ],
        )

        return DecisionOutput(
            agent=self.name,
            status=AgentStatus.SUCCESS,
            symbol=context.symbol,
            bias=TradeBias.WAIT,
            confidence=0.0,
            summary="Decision Agent initialized.",
            decision=decision,
        )
