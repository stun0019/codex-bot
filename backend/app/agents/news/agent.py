from __future__ import annotations

from ..base import BaseAgent
from ..models import (
    AgentName,
    AgentStatus,
    EvidenceItem,
    MarketContext,
    TradeBias,
)

from .analyzer import (
    NewsAnalyzer,
)

from .models import (
    NewsInput,
    NewsOutput,
)


class NewsAgent(
    BaseAgent[
        NewsInput,
        NewsOutput,
    ]
):
    """
    新聞分析 Agent。

    目前負責：

    1. 接收 NewsInput
    2. 呼叫 NewsAnalyzer
    3. 去重 / 分類新聞
    4. 判斷 affected symbols
    5. 建立初步 NewsEvent
    6. 根據事件重要程度產生 NewsOutput

    注意：

    目前尚未接入 LLM。

    因此：

    - 不直接判斷 LONG
    - 不直接判斷 SHORT
    - 不產生交易指令
    - bias 維持 NEUTRAL

    後續接入 LLM 後，
    才會做更完整的語意分析。
    """

    name = AgentName.NEWS

    def __init__(
        self,
        analyzer: NewsAnalyzer | None = None,
    ) -> None:

        super().__init__()

        self.analyzer = (
            analyzer
            if analyzer is not None
            else NewsAnalyzer()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: NewsInput,
    ) -> NewsOutput:
        """
        執行新聞分析。

        Pipeline:

            NewsInput
                ↓
            NewsAnalyzer
                ↓
            NewsEvent[]
                ↓
            NewsOutput
        """

        try:

            if not payload.articles:

                return NewsOutput(
                    agent=self.name,

                    status=AgentStatus.SKIPPED,

                    symbol=context.symbol,

                    bias=TradeBias.NEUTRAL,

                    confidence=0.0,

                    summary=(
                        "No news articles were provided."
                    ),

                    events=[],

                    data={
                        "articles_received": 0,
                        "events_generated": 0,
                        "focus_symbols": (
                            payload.focus_symbols
                        ),
                    },
                )

            events = (
                self.analyzer.analyze(
                    payload
                )
            )

            if not events:

                return NewsOutput(
                    agent=self.name,

                    status=AgentStatus.SUCCESS,

                    symbol=context.symbol,

                    bias=TradeBias.NEUTRAL,

                    confidence=0.0,

                    summary=(
                        "News analysis completed, "
                        "but no relevant events were identified."
                    ),

                    events=[],

                    data={
                        "articles_received":
                            len(
                                payload.articles
                            ),

                        "events_generated":
                            0,

                        "focus_symbols":
                            payload.focus_symbols,
                    },
                )

            highest_impact = max(
                event.impact_score
                for event
                in events
            )

            average_confidence = (
                sum(
                    event.confidence
                    for event
                    in events
                )
                / len(events)
            )

            relevant_events = [
                event
                for event
                in events
                if (
                    not payload.focus_symbols
                    or any(
                        symbol
                        in payload.focus_symbols
                        for symbol
                        in event.affected_symbols
                    )
                )
            ]

            evidence = []

            for event in events:

                source = (
                    ", ".join(
                        event.source_names
                    )
                    if event.source_names
                    else "unknown"
                )

                evidence.append(
                    EvidenceItem(
                        source=source,

                        description=(
                            event.title
                        ),

                        value={
                            "category":
                                event.category.value,

                            "impact_score":
                                event.impact_score,

                            "confidence":
                                event.confidence,

                            "affected_symbols":
                                event.affected_symbols,

                            "bias":
                                event.bias.value,
                        },

                        timestamp=(
                            event.published_at
                            if event.published_at
                            is not None
                            else context.timestamp
                        ),
                    )
                )

            top_event = events[0]

            summary = (
                f"News analysis completed. "
                f"{len(events)} relevant event"
                f"{'' if len(events) == 1 else 's'} "
                f"identified. "
                f"Highest impact event: "
                f"{top_event.title}"
            )

            return NewsOutput(
                agent=self.name,

                status=AgentStatus.SUCCESS,

                symbol=context.symbol,

                # 尚未接 LLM，
                # 因此 deterministic analyzer
                # 不決定市場方向。
                bias=TradeBias.NEUTRAL,

                confidence=min(
                    1.0,
                    max(
                        0.0,
                        average_confidence,
                    ),
                ),

                summary=summary,

                evidence=evidence,

                events=events,

                data={
                    "articles_received":
                        len(
                            payload.articles
                        ),

                    "events_generated":
                        len(events),

                    "relevant_events":
                        len(
                            relevant_events
                        ),

                    "focus_symbols":
                        payload.focus_symbols,

                    "highest_impact_score":
                        highest_impact,

                    "average_confidence":
                        round(
                            average_confidence,
                            6,
                        ),

                    "top_event":
                        top_event.title,

                    "top_event_category":
                        top_event.category.value,

                    "llm_analysis":
                        False,
                },
            )

        except Exception as exc:

            return NewsOutput(
                agent=self.name,

                status=AgentStatus.ERROR,

                symbol=context.symbol,

                bias=TradeBias.NEUTRAL,

                confidence=0.0,

                summary=(
                    "News analysis failed."
                ),

                events=[],

                data={
                    "articles_received":
                        len(
                            payload.articles
                        ),

                    "focus_symbols":
                        payload.focus_symbols,

                    "error_type":
                        type(exc).__name__,

                    "error":
                        str(exc),

                    "llm_analysis":
                        False,
                },

                errors=[
                    str(exc)
                ],
            )
