from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    MarketContext,
    TradeBias,
)

from .models import (
    RiskInput,
    RiskOutput,
)


class RiskAgent(
    BaseAgent[RiskInput, RiskOutput]
):
    """
    AI 風險分析員。

    注意：
    Risk Agent 不是最終硬性風控。

    未來真正交易時還需要獨立的
    deterministic risk engine。

    AI 不可以自行修改硬性風控限制。
    """

    name = AgentName.RISK

    async def analyze(
        self,
        context: MarketContext,
        payload: RiskInput,
    ) -> RiskOutput:

        return RiskOutput(
            agent=self.name,
            status=AgentStatus.SUCCESS,
            symbol=context.symbol,
            bias=TradeBias.NEUTRAL,
            confidence=0.0,
            summary="Risk Agent initialized.",
            approved=False,
            checks=[],
            data={
                "has_proposed_trade": bool(
                    payload.proposed_trade
                ),
            },
        )
