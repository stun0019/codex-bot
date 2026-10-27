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

from .scanner import (
    ScoutScanner,
)


class ScoutAgent(
    BaseAgent[ScoutInput, ScoutOutput]
):
    """
    市場機會掃描 Agent。

    工作：

    1. 接收 ScoutInput
    2. 呼叫 ScoutScanner
    3. 掃描 OKX USDT-SWAP 市場
    4. 取得市場候選標的
    5. 將結果包裝成 ScoutOutput

    注意：

    Scout Agent 不負責：

    - 判斷 LONG
    - 判斷 SHORT
    - 決定進場
    - 決定止損
    - 決定止盈
    - 執行交易

    Scout 的工作只有：

        找出目前值得其他 Agent
        進一步研究的市場。
    """

    name = AgentName.SCOUT

    def __init__(
        self,
        scanner: ScoutScanner | None = None,
    ) -> None:

        super().__init__()

        self.scanner = scanner

    async def analyze(
        self,
        context: MarketContext,
        payload: ScoutInput,
    ) -> ScoutOutput:
        """
        執行市場掃描。

        如果 payload.symbols 為空：

            掃描全部 OKX USDT-SWAP

        如果 payload.symbols 有指定：

            只掃描指定市場
        """

        try:

            symbols = (
                payload.symbols
                if payload.symbols
                else None
            )

            if self.scanner is not None:

                candidates = (
                    await self.scanner.scan(
                        symbols=symbols
                    )
                )

            else:

                async with ScoutScanner() as scanner:

                    candidates = (
                        await scanner.scan(
                            symbols=symbols
                        )
                    )

            if candidates:

                highest_score = max(
                    candidate.score
                    for candidate
                    in candidates
                )

                summary = (
                    f"Scout scan completed. "
                    f"{len(candidates)} market "
                    f"candidates identified."
                )

            else:

                highest_score = 0.0

                summary = (
                    "Scout scan completed. "
                    "No market candidates identified."
                )

            return ScoutOutput(
                agent=self.name,

                status=AgentStatus.SUCCESS,

                symbol=context.symbol,

                bias=TradeBias.NEUTRAL,

                confidence=highest_score,

                summary=summary,

                candidates=candidates,

                data={
                    "mode": (
                        "selected_symbols"
                        if symbols
                        else "all_usdt_swaps"
                    ),

                    "symbols_requested": (
                        symbols
                        or []
                    ),

                    "candidate_count":
                        len(candidates),

                    "top_candidate": (
                        candidates[0].symbol
                        if candidates
                        else None
                    ),

                    "top_score": (
                        candidates[0].score
                        if candidates
                        else None
                    ),
                },
            )

        except Exception as exc:

            return ScoutOutput(
                agent=self.name,

                status=AgentStatus.ERROR,

                symbol=context.symbol,

                bias=TradeBias.NEUTRAL,

                confidence=0.0,

                summary=(
                    "Scout market scan failed."
                ),

                candidates=[],

                data={
                    "error_type":
                        type(exc).__name__,

                    "error":
                        str(exc),

                    "symbols_requested":
                        payload.symbols,
                },
            )
