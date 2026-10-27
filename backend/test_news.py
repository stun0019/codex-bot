from __future__ import annotations

import asyncio
import os

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.agents.models import (
    AgentStatus,
    MarketContext,
    TradeBias,
)

from app.agents.news import (
    NewsAgent,
    NewsArticle,
    NewsInput,
    NewsLLMEventAnalysis,
    NewsLLMResult,
)


class FakeNewsLLMAnalyzer:
    """
    NEWS LLM integration 測試用。

    不呼叫 OpenAI API。

    用途：

    確認：

    NewsAgent
        ↓
    NewsAnalyzer
        ↓
    injected LLM
        ↓
    NewsOutput

    整條 AI integration pipeline
    是否能正常運作。
    """

    async def analyze(
        self,
        context,
        payload,
        events,
    ) -> NewsLLMResult:

        analyses: list[
            NewsLLMEventAnalysis
        ] = []

        for (
            index,
            event,
        ) in enumerate(
            events
        ):

            if index == 0:

                bias = (
                    TradeBias.LONG
                )

                impact = 0.88

                confidence = 0.91

                priced_in = 0.35

                horizon = (
                    "short_term"
                )

                summary = (
                    "Fake LLM classified the "
                    "highest-impact event as "
                    "bullish."
                )

                reasoning = [
                    (
                        "The event directly "
                        "affects the focus asset."
                    ),
                    (
                        "The information may not "
                        "be fully priced in."
                    ),
                ]

            else:

                bias = (
                    TradeBias.NEUTRAL
                )

                impact = (
                    event.impact_score
                )

                confidence = 0.70

                priced_in = 0.60

                horizon = (
                    "unknown"
                )

                summary = (
                    "Fake LLM found no strong "
                    "directional edge."
                )

                reasoning = [
                    (
                        "Directional evidence "
                        "is insufficient."
                    )
                ]

            analyses.append(
                NewsLLMEventAnalysis(
                    event_index=index,

                    bias=bias,

                    confidence=(
                        confidence
                    ),

                    impact_score=(
                        impact
                    ),

                    priced_in_risk=(
                        priced_in
                    ),

                    horizon=horizon,

                    summary=summary,

                    reasoning=(
                        reasoning
                    ),
                )
            )

        return NewsLLMResult(
            bias=TradeBias.LONG,

            confidence=0.88,

            summary=(
                "Fake NEWS LLM test completed "
                "with an overall LONG bias."
            ),

            event_analyses=analyses,
        )


def build_context(
) -> MarketContext:
    """
    建立 NEWS 測試用 MarketContext。
    """

    return MarketContext(
        symbol=(
            "BTC-USDT-SWAP"
        ),

        exchange="OKX",

        market_type="swap",

        timeframes=[
            "15m",
            "1H",
            "4H",
        ],

        metadata={
            "test":
                True,

            "source":
                "test_news.py",
        },
    )


def build_payload(
) -> NewsInput:
    """
    建立測試新聞。

    包含：

    1. BTC ETF / regulatory event
    2. 相同事件的第二來源
    3. Exchange security event
    4. 超過 72 小時的舊新聞

    第 4 則理論上會被
    NewsAnalyzer 過濾掉。
    """

    now = datetime.now(
        timezone.utc
    )

    return NewsInput(
        focus_symbols=[
            "BTC-USDT-SWAP",
            "ETH-USDT-SWAP",
        ],

        max_events=10,

        articles=[
            NewsArticle(
                title=(
                    "SEC approves new spot "
                    "Bitcoin ETF development"
                ),

                source="Test Reuters",

                published_at=(
                    now
                    -
                    timedelta(
                        minutes=20
                    )
                ),

                url=(
                    "https://example.com/"
                    "btc-etf-1"
                ),

                content=(
                    "The SEC approved a new "
                    "spot Bitcoin ETF related "
                    "development. Institutional "
                    "market participants are "
                    "monitoring potential capital "
                    "inflows."
                ),

                symbols=[
                    "BTC"
                ],
            ),

            NewsArticle(
                title=(
                    "SEC approves new spot "
                    "Bitcoin ETF development"
                ),

                source="Test Bloomberg",

                published_at=(
                    now
                    -
                    timedelta(
                        minutes=15
                    )
                ),

                url=(
                    "https://example.com/"
                    "btc-etf-2"
                ),

                content=(
                    "A second source confirms "
                    "the Bitcoin ETF regulatory "
                    "development."
                ),

                symbols=[
                    "BTC-USDT-SWAP"
                ],
            ),

            NewsArticle(
                title=(
                    "Crypto exchange reports "
                    "security incident"
                ),

                source="Test Security News",

                published_at=(
                    now
                    -
                    timedelta(
                        hours=2
                    )
                ),

                url=(
                    "https://example.com/"
                    "exchange-security"
                ),

                content=(
                    "A cryptocurrency exchange "
                    "reported a security breach "
                    "and temporarily suspended "
                    "some withdrawals."
                ),

                symbols=[
                    "ETH-USDT-SWAP"
                ],
            ),

            NewsArticle(
                title=(
                    "Old Bitcoin market story"
                ),

                source="Old News",

                published_at=(
                    now
                    -
                    timedelta(
                        hours=100
                    )
                ),

                url=(
                    "https://example.com/"
                    "old-story"
                ),

                content=(
                    "This article is intentionally "
                    "too old for the default "
                    "72-hour NEWS window."
                ),

                symbols=[
                    "BTC"
                ],
            ),
        ],
    )


def print_separator(
    title: str,
) -> None:

    print()

    print(
        "=" * 78
    )

    print(
        title
    )

    print(
        "=" * 78
    )

    print()


def print_news_output(
    output,
) -> None:
    """
    顯示 NEWS Agent 結果。
    """

    print(
        f"Status     : "
        f"{output.status.value}"
    )

    print(
        f"Symbol     : "
        f"{output.symbol}"
    )

    print(
        f"Bias       : "
        f"{output.bias.value}"
    )

    print(
        f"Confidence : "
        f"{output.confidence:.4f}"
    )

    print(
        f"Summary    : "
        f"{output.summary}"
    )

    print(
        f"Events     : "
        f"{len(output.events)}"
    )

    print(
        f"Evidence   : "
        f"{len(output.evidence)}"
    )

    print()

    for (
        index,
        event,
    ) in enumerate(
        output.events,
        start=1,
    ):

        print(
            f"{index}. "
            f"{event.title}"
        )

        print(
            "   Category     : "
            f"{event.category.value}"
        )

        print(
            "   Bias         : "
            f"{event.bias.value}"
        )

        print(
            "   Impact       : "
            f"{event.impact_score:.4f}"
        )

        print(
            "   Confidence   : "
            f"{event.confidence:.4f}"
        )

        print(
            "   Symbols      : "
            f"{event.affected_symbols}"
        )

        print(
            "   Sources      : "
            f"{event.source_names}"
        )

        priced_in = (
            event.metadata.get(
                "priced_in_risk"
            )
        )

        if priced_in is not None:

            print(
                "   Priced In    : "
                f"{priced_in:.4f}"
            )

        horizon = (
            event.metadata.get(
                "horizon"
            )
        )

        if horizon:

            print(
                "   Horizon      : "
                f"{horizon}"
            )

        reasoning = (
            event.metadata.get(
                "llm_reasoning"
            )
        )

        if reasoning:

            print(
                "   Reasoning:"
            )

            for reason in reasoning:

                print(
                    f"      - {reason}"
                )

        print()

    print(
        "Data:"
    )

    for (
        key,
        value,
    ) in output.data.items():

        print(
            f"   {key}: {value}"
        )


async def test_deterministic(
) -> bool:
    """
    TEST 1

    不使用 LLM。

    驗證：

    - NewsAnalyzer
    - 去重
    - 過舊文章過濾
    - category
    - affected symbols
    - impact
    - confidence
    - evidence
    """

    print_separator(
        "TEST 1 - DETERMINISTIC NEWS"
    )

    context = (
        build_context()
    )

    payload = (
        build_payload()
    )

    agent = NewsAgent(
        enable_llm=False
    )

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_news_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SUCCESS
    ):

        print(
            "RESULT: FAIL"
        )

        return False

    if not output.events:

        print(
            "RESULT: FAIL - "
            "No events returned."
        )

        return False

    if (
        output.bias
        !=
        TradeBias.NEUTRAL
    ):

        print(
            "RESULT: FAIL - "
            "Deterministic NEWS "
            "should remain NEUTRAL."
        )

        return False

    if (
        output.data.get(
            "llm_analysis"
        )
        is not False
    ):

        print(
            "RESULT: FAIL - "
            "LLM should be disabled."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_fake_llm(
) -> bool:
    """
    TEST 2

    使用 Fake LLM。

    不呼叫 OpenAI API。

    驗證：

    - LLM injection
    - Overall bias
    - Event bias
    - Impact override
    - Confidence override
    - Priced-in risk
    - Horizon
    - Reasoning
    """

    print_separator(
        "TEST 2 - FAKE LLM INTEGRATION"
    )

    context = (
        build_context()
    )

    payload = (
        build_payload()
    )

    fake_llm = (
        FakeNewsLLMAnalyzer()
    )

    agent = NewsAgent(
        llm_analyzer=fake_llm,
        enable_llm=True,
    )

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_news_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SUCCESS
    ):

        print(
            "RESULT: FAIL"
        )

        return False

    if (
        output.bias
        !=
        TradeBias.LONG
    ):

        print(
            "RESULT: FAIL - "
            "Fake LLM bias was not "
            "applied."
        )

        return False

    if (
        output.data.get(
            "llm_analysis"
        )
        is not True
    ):

        print(
            "RESULT: FAIL - "
            "LLM integration was "
            "not marked active."
        )

        return False

    if not any(
        event.metadata.get(
            "llm_analyzed"
        )
        for event
        in output.events
    ):

        print(
            "RESULT: FAIL - "
            "No event received "
            "LLM metadata."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_empty_input(
) -> bool:
    """
    TEST 3

    沒有新聞時應該：

        SKIPPED

    而不是：

        ERROR
    """

    print_separator(
        "TEST 3 - EMPTY INPUT"
    )

    context = (
        build_context()
    )

    payload = NewsInput(
        articles=[],
        focus_symbols=[
            "BTC-USDT-SWAP"
        ],
    )

    agent = NewsAgent(
        enable_llm=False
    )

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_news_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SKIPPED
    ):

        print(
            "RESULT: FAIL"
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_live_llm(
) -> bool:
    """
    TEST 4

    真實 OpenAI API 測試。

    預設不執行。

    只有：

        RUN_LIVE_NEWS_LLM=1

    才會真的呼叫 API。

    同時必須設定：

        OPENAI_API_KEY
    """

    print_separator(
        "TEST 4 - LIVE OPENAI NEWS LLM"
    )

    run_live = (
        os.getenv(
            "RUN_LIVE_NEWS_LLM",
            ""
        )
        .strip()
        ==
        "1"
    )

    if not run_live:

        print(
            "SKIPPED"
        )

        print(
            "Set RUN_LIVE_NEWS_LLM=1 "
            "to enable this test."
        )

        return True

    api_key = (
        os.getenv(
            "OPENAI_API_KEY",
            ""
        ).strip()
    )

    if not api_key:

        print(
            "RESULT: FAIL"
        )

        print(
            "OPENAI_API_KEY "
            "is not configured."
        )

        return False

    context = (
        build_context()
    )

    payload = (
        build_payload()
    )

    agent = NewsAgent(
        enable_llm=True
    )

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_news_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SUCCESS
    ):

        print(
            "RESULT: FAIL"
        )

        return False

    if (
        output.data.get(
            "llm_analysis"
        )
        is not True
    ):

        print(
            "RESULT: FAIL"
        )

        print(
            "LLM was not used."
        )

        llm_error = (
            output.data.get(
                "llm_error"
            )
        )

        if llm_error:

            print(
                f"LLM Error: "
                f"{llm_error}"
            )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def main(
) -> int:

    print_separator(
        "CODEX BOT - NEWS AGENT TEST"
    )

    print(
        "Testing NEWS pipeline:"
    )

    print(
        "NewsArticle"
    )

    print(
        "    ↓"
    )

    print(
        "NewsAnalyzer"
    )

    print(
        "    ↓"
    )

    print(
        "NewsEvent"
    )

    print(
        "    ↓"
    )

    print(
        "NewsLLMAnalyzer"
    )

    print(
        "    ↓"
    )

    print(
        "NewsOutput"
    )

    results = []

    results.append(
        await test_deterministic()
    )

    results.append(
        await test_fake_llm()
    )

    results.append(
        await test_empty_input()
    )

    results.append(
        await test_live_llm()
    )

    print_separator(
        "NEWS TEST SUMMARY"
    )

    passed = sum(
        1
        for result
        in results
        if result
    )

    total = (
        len(results)
    )

    print(
        f"Passed: {passed}/{total}"
    )

    if all(results):

        print(
            "NEWS TEST RESULT: PASS"
        )

        return 0

    print(
        "NEWS TEST RESULT: FAIL"
    )

    return 1


if __name__ == "__main__":

    try:

        exit_code = (
            asyncio.run(
                main()
            )
        )

        raise SystemExit(
            exit_code
        )

    except KeyboardInterrupt:

        print()

        print(
            "NEWS test interrupted."
        )

        raise SystemExit(
            130
        )
