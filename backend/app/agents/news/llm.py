from __future__ import annotations

import json
import os

from dataclasses import (
    dataclass,
    field,
)
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ..models import (
    MarketContext,
    TradeBias,
)

from .models import (
    NewsEvent,
    NewsInput,
)


class NewsLLMEventAnalysis(BaseModel):
    """
    LLM 對單一 NewsEvent 的分析結果。
    """

    event_index: int = Field(
        ge=0
    )

    bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    impact_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    priced_in_risk: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    horizon: str = "unknown"

    summary: str = ""

    reasoning: list[str] = Field(
        default_factory=list
    )


class NewsLLMResult(BaseModel):
    """
    NEWS LLM 最終結果。

    bias:
        NEWS Agent 對指定市場的
        整體新聞方向判斷。

    confidence:
        對整體新聞方向判斷的信心。

    注意：

    這仍然不是交易指令。
    """

    bias: TradeBias = (
        TradeBias.NEUTRAL
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    summary: str = ""

    event_analyses: list[
        NewsLLMEventAnalysis
    ] = Field(
        default_factory=list
    )


@dataclass(slots=True)
class NewsLLMConfig:
    """
    NEWS LLM 設定。

    OPENAI_NEWS_MODEL
        可透過環境變數覆蓋模型。

    OPENAI_API_KEY
        由 OpenAI SDK 自動從
        環境變數讀取。

    API Key 不可寫入 Git。
    """

    model: str = field(
        default_factory=lambda:
            os.getenv(
                "OPENAI_NEWS_MODEL",
                "gpt-6-luna",
            )
    )

    max_articles: int = 30

    max_content_chars: int = 4000

    max_events: int = 10


class NewsLLMAnalyzer:
    """
    NEWS Agent 的 AI semantic analyzer。

    Pipeline:

        NewsInput
            ↓
        NewsAnalyzer
            ↓
        deterministic NewsEvent[]
            ↓
        NewsLLMAnalyzer
            ↓
        semantic market analysis
            ↓
        LONG / SHORT / NEUTRAL
            ↓
        confidence / reasoning
            ↓
        NewsLLMResult

    注意：

    此類別：

    - 不下單
    - 不決定倉位
    - 不設定槓桿
    - 不設定 SL / TP
    - 不接觸交易所私人 API

    只負責新聞語意分析。
    """

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        config: NewsLLMConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else NewsLLMConfig()
        )

        self.client = (
            client
            if client is not None
            else AsyncOpenAI()
        )

        self._owns_client = (
            client is None
        )


    async def __aenter__(
        self,
    ) -> "NewsLLMAnalyzer":

        return self


    async def __aexit__(
        self,
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:

        await self.close()


    async def close(
        self,
    ) -> None:
        """
        關閉 OpenAI async client。
        """

        if self._owns_client:

            await self.client.close()


    async def analyze(
        self,
        context: MarketContext,
        payload: NewsInput,
        events: list[NewsEvent],
    ) -> NewsLLMResult:
        """
        使用 LLM 分析新聞。

        若 events 為空，
        直接回 NEUTRAL。
        """

        if not events:

            return NewsLLMResult(
                bias=TradeBias.NEUTRAL,
                confidence=0.0,
                summary=(
                    "No news events were available "
                    "for AI analysis."
                ),
                event_analyses=[],
            )


        prepared_articles = (
            self._prepare_articles(
                payload
            )
        )


        prepared_events = (
            self._prepare_events(
                events
            )
        )


        user_payload = {
            "market_context": {
                "symbol":
                    context.symbol,

                "exchange":
                    context.exchange,

                "market_type":
                    context.market_type,

                "timestamp":
                    context.timestamp.isoformat(),

                "timeframes":
                    context.timeframes,
            },

            "focus_symbols":
                payload.focus_symbols,

            "articles":
                prepared_articles,

            "pre_analyzed_events":
                prepared_events,
        }


        response = (
            await self.client.responses.create(
                model=self.config.model,

                instructions=(
                    self._system_instructions()
                ),

                input=(
                    json.dumps(
                        user_payload,
                        ensure_ascii=False,
                        separators=(
                            ",",
                            ":",
                        ),
                    )
                ),

                text={
                    "format": {
                        "type":
                            "json_schema",

                        "name":
                            "news_market_analysis",

                        "strict":
                            True,

                        "schema":
                            self._response_schema(),
                    },

                    "verbosity":
                        "low",
                },
            )
        )


        output_text = (
            response.output_text
            or ""
        ).strip()


        if not output_text:

            raise ValueError(
                "OpenAI returned an empty "
                "NEWS analysis."
            )


        try:

            raw = json.loads(
                output_text
            )

        except json.JSONDecodeError as exc:

            raise ValueError(
                "OpenAI NEWS response was "
                "not valid JSON."
            ) from exc


        result = (
            NewsLLMResult.model_validate(
                raw
            )
        )


        return self._validate_result(
            result=result,
            event_count=len(
                prepared_events
            ),
        )


    def _prepare_articles(
        self,
        payload: NewsInput,
    ) -> list[dict[str, Any]]:
        """
        將原始文章縮減成適合送給 LLM 的格式。

        避免：

        - 無限長文章
        - metadata 全部送進模型
        - 不必要 token 消耗
        """

        result: list[
            dict[str, Any]
        ] = []


        articles = (
            payload.articles[
                :self.config.max_articles
            ]
        )


        for (
            index,
            article,
        ) in enumerate(
            articles
        ):

            content = (
                article.content
                or ""
            )


            if (
                len(content)
                >
                self.config
                .max_content_chars
            ):

                content = (
                    content[
                        :self.config
                        .max_content_chars
                    ]
                )


            result.append(
                {
                    "article_index":
                        index,

                    "title":
                        article.title,

                    "source":
                        article.source,

                    "published_at":
                        (
                            article
                            .published_at
                            .isoformat()
                            if (
                                article
                                .published_at
                                is not None
                            )
                            else None
                        ),

                    "url":
                        article.url,

                    "symbols":
                        article.symbols,

                    "content":
                        content,
                }
            )


        return result


    def _prepare_events(
        self,
        events: list[NewsEvent],
    ) -> list[dict[str, Any]]:
        """
        將 deterministic analyzer
        產生的事件送給 LLM。

        LLM 可以重新評估：

        - bias
        - impact
        - confidence

        但不能改變事件 index。
        """

        prepared: list[
            dict[str, Any]
        ] = []


        for (
            index,
            event,
        ) in enumerate(
            events[
                :self.config.max_events
            ]
        ):

            prepared.append(
                {
                    "event_index":
                        index,

                    "title":
                        event.title,

                    "category":
                        event.category.value,

                    "affected_symbols":
                        event.affected_symbols,

                    "preliminary_impact_score":
                        event.impact_score,

                    "preliminary_confidence":
                        event.confidence,

                    "description":
                        event.description,

                    "source_names":
                        event.source_names,

                    "published_at":
                        (
                            event
                            .published_at
                            .isoformat()
                            if (
                                event
                                .published_at
                                is not None
                            )
                            else None
                        ),
                }
            )


        return prepared


    def _validate_result(
        self,
        result: NewsLLMResult,
        event_count: int,
    ) -> NewsLLMResult:
        """
        額外檢查 LLM 結果。

        防止：

        - event_index 超出範圍
        - 重複 event_index
        - NEWS 回 WAIT
        """

        valid_analyses: list[
            NewsLLMEventAnalysis
        ] = []


        seen_indexes: set[int] = (
            set()
        )


        for analysis in (
            result.event_analyses
        ):

            if (
                analysis.event_index
                >=
                event_count
            ):

                continue


            if (
                analysis.event_index
                in seen_indexes
            ):

                continue


            if (
                analysis.bias
                ==
                TradeBias.WAIT
            ):

                analysis.bias = (
                    TradeBias.NEUTRAL
                )


            seen_indexes.add(
                analysis.event_index
            )


            valid_analyses.append(
                analysis
            )


        result.event_analyses = (
            valid_analyses
        )


        if (
            result.bias
            ==
            TradeBias.WAIT
        ):

            result.bias = (
                TradeBias.NEUTRAL
            )


        return result


    @staticmethod
    def _system_instructions(
    ) -> str:
        """
        NEWS AI system instructions。

        核心原則：

        - 分析新聞，而不是交易
        - 避免單純 sentiment keyword
        - 注意新聞可能已 price in
        - 不把相關性當因果
        - 資訊不足時必須 NEUTRAL
        """

        return """
You are the NEWS analysis component of a
multi-agent cryptocurrency trading system.

Your task is to analyze the supplied news
articles and pre-analyzed events and estimate
their likely directional market implications.

You are NOT the final trading decision maker.

You must never:
- place trades
- recommend leverage
- recommend position size
- choose stop loss
- choose take profit
- claim guaranteed outcomes

For each event:

1. Determine whether the event is likely:
   - long
   - short
   - neutral

2. Estimate impact_score from 0.0 to 1.0.

3. Estimate confidence from 0.0 to 1.0.

4. Estimate priced_in_risk:
   - 0.0 means likely not priced in
   - 1.0 means likely fully priced in

5. Choose horizon:
   - immediate
   - short_term
   - medium_term
   - long_term
   - unknown

Analyze causal market impact, not merely
positive or negative language.

Consider:
- source quality
- recency
- whether multiple sources confirm the event
- whether the event directly affects the asset
- macroeconomic implications
- regulatory implications
- security incidents
- ETF / institutional flows
- exchange events
- protocol changes
- token supply changes
- whether the market may already have priced
  in the information

If evidence is weak, conflicting, stale, or
insufficient, prefer neutral and lower
confidence.

The overall bias must represent only the NEWS
component's view for the supplied market
context.

The final trading system will combine NEWS
with SCOUT, SENTIMENT, CHARTS, RISK and
DECISION.

Return only the requested structured output.
""".strip()


    @staticmethod
    def _response_schema(
    ) -> dict[str, Any]:
        """
        OpenAI Structured Output JSON schema。
        """

        bias_enum = [
            "long",
            "short",
            "neutral",
        ]


        horizon_enum = [
            "immediate",
            "short_term",
            "medium_term",
            "long_term",
            "unknown",
        ]


        return {
            "type":
                "object",

            "additionalProperties":
                False,

            "required": [
                "bias",
                "confidence",
                "summary",
                "event_analyses",
            ],

            "properties": {
                "bias": {
                    "type":
                        "string",

                    "enum":
                        bias_enum,
                },

                "confidence": {
                    "type":
                        "number",

                    "minimum":
                        0.0,

                    "maximum":
                        1.0,
                },

                "summary": {
                    "type":
                        "string",
                },

                "event_analyses": {
                    "type":
                        "array",

                    "items": {
                        "type":
                            "object",

                        "additionalProperties":
                            False,

                        "required": [
                            "event_index",
                            "bias",
                            "confidence",
                            "impact_score",
                            "priced_in_risk",
                            "horizon",
                            "summary",
                            "reasoning",
                        ],

                        "properties": {
                            "event_index": {
                                "type":
                                    "integer",

                                "minimum":
                                    0,
                            },

                            "bias": {
                                "type":
                                    "string",

                                "enum":
                                    bias_enum,
                            },

                            "confidence": {
                                "type":
                                    "number",

                                "minimum":
                                    0.0,

                                "maximum":
                                    1.0,
                            },

                            "impact_score": {
                                "type":
                                    "number",

                                "minimum":
                                    0.0,

                                "maximum":
                                    1.0,
                            },

                            "priced_in_risk": {
                                "type":
                                    "number",

                                "minimum":
                                    0.0,

                                "maximum":
                                    1.0,
                            },

                            "horizon": {
                                "type":
                                    "string",

                                "enum":
                                    horizon_enum,
                            },

                            "summary": {
                                "type":
                                    "string",
                            },

                            "reasoning": {
                                "type":
                                    "array",

                                "items": {
                                    "type":
                                        "string",
                                },
                            },
                        },
                    },
                },
            },
        }
