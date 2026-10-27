from __future__ import annotations

import os

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

from .llm import (
    NewsLLMAnalyzer,
    NewsLLMResult,
)

from .models import (
    NewsEvent,
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

    Pipeline:

        NewsInput
            ↓
        NewsAnalyzer
            ↓
        deterministic NewsEvent[]
            ↓
        NewsLLMAnalyzer
            ↓
        AI semantic analysis
            ↓
        NewsOutput

    NEWS Agent 負責：

    - 新聞去重
    - 新聞分類
    - Symbol 關聯
    - 事件重要度分析
    - 新聞方向分析
    - Priced-in risk 分析
    - 新聞影響時間尺度
    - Evidence 建立

    NEWS Agent 不負責：

    - 最終交易決策
    - 下單
    - 槓桿
    - 倉位大小
    - Stop Loss
    - Take Profit

    最終交易決策由 DECISION Agent 負責。
    """

    name = AgentName.NEWS

    def __init__(
        self,
        analyzer: NewsAnalyzer | None = None,
        llm_analyzer: NewsLLMAnalyzer | None = None,
        enable_llm: bool = True,
    ) -> None:

        super().__init__()

        self.analyzer = (
            analyzer
            if analyzer is not None
            else NewsAnalyzer()
        )

        self.llm_analyzer = (
            llm_analyzer
        )

        self.enable_llm = (
            enable_llm
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: NewsInput,
    ) -> NewsOutput:
        """
        執行 NEWS 分析。
        """

        try:

            if not payload.articles:

                return self._empty_output(
                    context=context,
                    payload=payload,
                )

            # ==============================
            # Deterministic pre-analysis
            # ==============================

            events = (
                self.analyzer.analyze(
                    payload
                )
            )

            if not events:

                return NewsOutput(
                    agent=self.name,

                    status=(
                        AgentStatus.SUCCESS
                    ),

                    symbol=context.symbol,

                    bias=(
                        TradeBias.NEUTRAL
                    ),

                    confidence=0.0,

                    summary=(
                        "News analysis completed, "
                        "but no relevant events "
                        "were identified."
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

                        "deterministic_analysis":
                            True,

                        "llm_analysis":
                            False,
                    },
                )

            # ==============================
            # Default deterministic result
            # ==============================

            output_events = (
                events
            )

            overall_bias = (
                TradeBias.NEUTRAL
            )

            overall_confidence = (
                self._average_confidence(
                    events
                )
            )

            top_event = (
                events[0]
            )

            summary = (
                f"News analysis completed. "
                f"{len(events)} event"
                f"{'' if len(events) == 1 else 's'} "
                f"identified. "
                f"Highest impact event: "
                f"{top_event.title}"
            )

            llm_used = False

            llm_error: str | None = (
                None
            )

            # ==============================
            # AI semantic analysis
            # ==============================

            if self._should_use_llm():

                try:

                    llm_result = (
                        await self._run_llm(
                            context=context,
                            payload=payload,
                            events=events,
                        )
                    )

                    output_events = (
                        self._apply_llm_result(
                            events=events,
                            result=llm_result,
                        )
                    )

                    overall_bias = (
                        llm_result.bias
                    )

                    overall_confidence = (
                        llm_result.confidence
                    )

                    if llm_result.summary:

                        summary = (
                            llm_result.summary
                        )

                    llm_used = True

                except Exception as exc:

                    # LLM failure 不應讓
                    # deterministic NEWS
                    # 整體失效。

                    llm_error = (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

            # ==============================
            # Evidence
            # ==============================

            evidence = (
                self._build_evidence(
                    context=context,
                    events=output_events,
                )
            )

            # ==============================
            # Statistics
            # ==============================

            highest_impact = max(
                event.impact_score
                for event
                in output_events
            )

            relevant_events = (
                self._relevant_events(
                    events=output_events,
                    focus_symbols=(
                        payload.focus_symbols
                    ),
                )
            )

            top_event = max(
                output_events,
                key=lambda event:
                    event.impact_score,
            )

            # ==============================
            # Final output
            # ==============================

            data = {
                "articles_received":
                    len(
                        payload.articles
                    ),

                "events_generated":
                    len(
                        output_events
                    ),

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
                        self._average_confidence(
                            output_events
                        ),
                        6,
                    ),

                "top_event":
                    top_event.title,

                "top_event_category":
                    top_event.category.value,

                "deterministic_analysis":
                    True,

                "llm_analysis":
                    llm_used,
            }

            if llm_error:

                data[
                    "llm_error"
                ] = llm_error

            return NewsOutput(
                agent=self.name,

                status=(
                    AgentStatus.SUCCESS
                ),

                symbol=context.symbol,

                bias=overall_bias,

                confidence=(
                    self._clamp_score(
                        overall_confidence
                    )
                ),

                summary=summary,

                evidence=evidence,

                events=output_events,

                data=data,
            )

        except Exception as exc:

            return NewsOutput(
                agent=self.name,

                status=(
                    AgentStatus.ERROR
                ),

                symbol=context.symbol,

                bias=(
                    TradeBias.NEUTRAL
                ),

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

    # ==============================
    # LLM
    # ==============================

    def _should_use_llm(
        self,
    ) -> bool:
        """
        判斷目前是否應使用 LLM。

        Injected llm_analyzer
        不要求 OPENAI_API_KEY，
        因為測試或其他 client
        可能自行處理 authentication。
        """

        if not self.enable_llm:

            return False

        if (
            self.llm_analyzer
            is not None
        ):

            return True

        api_key = (
            os.getenv(
                "OPENAI_API_KEY"
            )
        )

        return bool(
            api_key
            and api_key.strip()
        )

    async def _run_llm(
        self,
        context: MarketContext,
        payload: NewsInput,
        events: list[NewsEvent],
    ) -> NewsLLMResult:
        """
        執行 NewsLLMAnalyzer。

        如果 NewsAgent 收到外部 injected
        analyzer，不會主動 close。

        如果由 NewsAgent 自己建立，
        則使用 async context manager
        自動關閉 client。
        """

        if (
            self.llm_analyzer
            is not None
        ):

            return (
                await self.llm_analyzer
                .analyze(
                    context=context,
                    payload=payload,
                    events=events,
                )
            )

        async with (
            NewsLLMAnalyzer()
            as analyzer
        ):

            return (
                await analyzer.analyze(
                    context=context,
                    payload=payload,
                    events=events,
                )
            )

    # ==============================
    # Apply AI result
    # ==============================

    def _apply_llm_result(
        self,
        events: list[NewsEvent],
        result: NewsLLMResult,
    ) -> list[NewsEvent]:
        """
        將 LLM event analysis
        套回 deterministic NewsEvent。

        不直接修改原始 event，
        使用 Pydantic model_copy。
        """

        analysis_map = {
            analysis.event_index:
                analysis

            for analysis
            in result.event_analyses
        }

        updated_events: list[
            NewsEvent
        ] = []

        for (
            index,
            event,
        ) in enumerate(
            events
        ):

            analysis = (
                analysis_map.get(
                    index
                )
            )

            if analysis is None:

                updated_events.append(
                    event
                )

                continue

            metadata = dict(
                event.metadata
            )

            metadata.update(
                {
                    "llm_analyzed":
                        True,

                    "priced_in_risk":
                        analysis
                        .priced_in_risk,

                    "horizon":
                        analysis
                        .horizon,

                    "llm_reasoning":
                        analysis
                        .reasoning,

                    "deterministic_impact_score":
                        event
                        .impact_score,

                    "deterministic_confidence":
                        event
                        .confidence,
                }
            )

            description = (
                analysis.summary
                or event.description
            )

            updated = (
                event.model_copy(
                    update={
                        "bias":
                            analysis.bias,

                        "impact_score":
                            self._clamp_score(
                                analysis
                                .impact_score
                            ),

                        "confidence":
                            self._clamp_score(
                                analysis
                                .confidence
                            ),

                        "description":
                            description,

                        "metadata":
                            metadata,
                    }
                )
            )

            updated_events.append(
                updated
            )

        updated_events.sort(
            key=lambda event: (
                event.impact_score,
                event.confidence,
            ),
            reverse=True,
        )

        return updated_events

    # ==============================
    # Evidence
    # ==============================

    def _build_evidence(
        self,
        context: MarketContext,
        events: list[NewsEvent],
    ) -> list[EvidenceItem]:
        """
        將 NewsEvent 轉換成
        AgentOutput evidence。
        """

        evidence: list[
            EvidenceItem
        ] = []

        for event in events:

            source = (
                ", ".join(
                    event.source_names
                )
                if event.source_names
                else "unknown"
            )

            value = {
                "category":
                    event.category.value,

                "bias":
                    event.bias.value,

                "impact_score":
                    event.impact_score,

                "confidence":
                    event.confidence,

                "affected_symbols":
                    event.affected_symbols,
            }

            priced_in_risk = (
                event.metadata.get(
                    "priced_in_risk"
                )
            )

            if (
                priced_in_risk
                is not None
            ):

                value[
                    "priced_in_risk"
                ] = priced_in_risk

            horizon = (
                event.metadata.get(
                    "horizon"
                )
            )

            if horizon:

                value[
                    "horizon"
                ] = horizon

            reasoning = (
                event.metadata.get(
                    "llm_reasoning"
                )
            )

            if reasoning:

                value[
                    "reasoning"
                ] = reasoning

            evidence.append(
                EvidenceItem(
                    source=source,

                    description=(
                        event.title
                    ),

                    value=value,

                    timestamp=(
                        event.published_at
                        if (
                            event.published_at
                            is not None
                        )
                        else context.timestamp
                    ),
                )
            )

        return evidence

    # ==============================
    # Helpers
    # ==============================

    def _empty_output(
        self,
        context: MarketContext,
        payload: NewsInput,
    ) -> NewsOutput:
        """
        沒有新聞輸入時的結果。
        """

        return NewsOutput(
            agent=self.name,

            status=(
                AgentStatus.SKIPPED
            ),

            symbol=context.symbol,

            bias=(
                TradeBias.NEUTRAL
            ),

            confidence=0.0,

            summary=(
                "No news articles were provided."
            ),

            events=[],

            data={
                "articles_received":
                    0,

                "events_generated":
                    0,

                "focus_symbols":
                    payload.focus_symbols,

                "deterministic_analysis":
                    False,

                "llm_analysis":
                    False,
            },
        )

    @staticmethod
    def _average_confidence(
        events: list[NewsEvent],
    ) -> float:
        """
        計算平均 confidence。
        """

        if not events:

            return 0.0

        return (
            sum(
                event.confidence
                for event
                in events
            )
            /
            len(events)
        )

    @classmethod
    def _relevant_events(
        cls,
        events: list[NewsEvent],
        focus_symbols: list[str],
    ) -> list[NewsEvent]:
        """
        找出與 focus symbols
        有直接關聯的事件。

        BTC 與 BTC-USDT-SWAP
        會視為同一個 underlying。
        """

        if not focus_symbols:

            return events

        normalized_focus = {
            cls._symbol_key(
                symbol
            )

            for symbol
            in focus_symbols

            if symbol
        }

        normalized_focus.discard(
            ""
        )

        return [
            event

            for event
            in events

            if any(
                cls._symbol_key(
                    symbol
                )
                in normalized_focus

                for symbol
                in event.affected_symbols

                if symbol
            )
        ]

    @staticmethod
    def _symbol_key(
        symbol: str,
    ) -> str:
        """
        將：

            BTC
            BTC-USDT
            BTC-USDT-SWAP

        都轉成：

            BTC

        用於 symbol 關聯比較。
        """

        if not symbol:

            return ""

        normalized = (
            symbol
            .strip()
            .upper()
        )

        return (
            normalized
            .split("-")[0]
        )

    @staticmethod
    def _clamp_score(
        value: float,
    ) -> float:
        """
        保證 score 位於 0 ~ 1。
        """

        return max(
            0.0,
            min(
                1.0,
                float(
                    value
                ),
            ),
        )
