from __future__ import annotations

import asyncio

from app.agents.models import (
    AgentStatus,
    MarketContext,
    TradeBias,
)

from app.agents.sentiment import (
    CrowdingSide,
    SentimentAgent,
    SentimentAnalyzer,
    SentimentInput,
    SentimentRegime,
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


def build_context(
    symbol: str = "BTC-USDT-SWAP",
) -> MarketContext:

    return MarketContext(
        symbol=symbol,

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
                "test_sentiment.py",
        },
    )


def print_output(
    output,
) -> None:

    print(
        f"Status       : "
        f"{output.status.value}"
    )

    print(
        f"Symbol       : "
        f"{output.symbol}"
    )

    print(
        f"Bias         : "
        f"{output.bias.value}"
    )

    print(
        f"Confidence   : "
        f"{output.confidence:.4f}"
    )

    print(
        f"Regime       : "
        f"{output.regime.value}"
    )

    print(
        f"Crowding     : "
        f"{output.crowding_side.value}"
    )

    print(
        f"Composite    : "
        f"{output.metrics.composite_score:+.4f}"
    )

    print(
        f"CrowdingScore: "
        f"{output.metrics.crowding_score:.4f}"
    )

    print(
        f"Data Quality : "
        f"{output.metrics.data_quality_score:.4f}"
    )

    print(
        f"Disagreement : "
        f"{output.metrics.disagreement_score:.4f}"
    )

    print(
        f"Signals      : "
        f"{output.metrics.signal_count}"
    )

    print(
        f"Evidence     : "
        f"{len(output.evidence)}"
    )

    print(
        f"Summary      : "
        f"{output.summary}"
    )

    print()

    for (
        index,
        signal,
    ) in enumerate(
        output.signals,
        start=1,
    ):

        print(
            f"{index}. "
            f"{signal.name}"
        )

        print(
            f"   Source      : "
            f"{signal.source.value}"
        )

        print(
            f"   Score       : "
            f"{signal.score:+.4f}"
        )

        print(
            f"   Confidence  : "
            f"{signal.confidence:.4f}"
        )

        print(
            f"   Crowding    : "
            f"{signal.crowding_score:.4f}"
        )

        print(
            f"   Bias        : "
            f"{signal.directional_bias.value}"
        )

        print(
            f"   Value       : "
            f"{signal.value}"
        )

        print(
            f"   Description : "
            f"{signal.description}"
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


async def test_bullish_crowded(
) -> bool:
    """
    TEST 1

    強烈 bullish positioning：

    - positive funding
    - OI 上升
    - price 上升
    - long/short ratio 高
    - social bullish
    - short liquidations dominant

    預期：

    - SUCCESS
    - LONG
    - bullish / extreme bullish
    - LONG crowding
    """

    print_separator(
        "TEST 1 - BULLISH + LONG CROWDED"
    )

    context = (
        build_context()
    )

    payload = SentimentInput(
        funding_rate_data={
            "funding_rate":
                0.00085,
        },

        open_interest_data={
            "change_pct":
                11.5,
        },

        long_short_ratio_data={
            "ratio":
                1.72,
        },

        social_data={
            "score":
                0.68,

            "sample_size":
                12000,
        },

        liquidation_data={
            "long_liquidations":
                1_000_000,

            "short_liquidations":
                4_500_000,
        },

        market_activity_data={
            "price_change_pct":
                4.2,
        },
    )

    agent = SentimentAgent()

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SUCCESS
    ):

        print(
            "RESULT: FAIL - "
            "Expected SUCCESS."
        )

        return False

    if (
        output.bias
        !=
        TradeBias.LONG
    ):

        print(
            "RESULT: FAIL - "
            "Expected LONG bias."
        )

        return False

    if (
        output.regime
        not in (
            SentimentRegime.BULLISH,
            SentimentRegime.EXTREME_BULLISH,
        )
    ):

        print(
            "RESULT: FAIL - "
            "Expected bullish regime."
        )

        return False

    if (
        output.crowding_side
        !=
        CrowdingSide.LONG
    ):

        print(
            "RESULT: FAIL - "
            "Expected LONG crowding."
        )

        return False

    if (
        output.metrics.signal_count
        < 4
    ):

        print(
            "RESULT: FAIL - "
            "Too few sentiment signals."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_bearish_crowded(
) -> bool:
    """
    TEST 2

    強烈 bearish positioning。

    預期：

    - SHORT
    - bearish / extreme bearish
    - SHORT crowding
    """

    print_separator(
        "TEST 2 - BEARISH + SHORT CROWDED"
    )

    context = (
        build_context(
            "ETH-USDT-SWAP"
        )
    )

    payload = SentimentInput(
        funding_rate_data={
            "funding_rate":
                -0.00090,
        },

        open_interest_data={
            "change_pct":
                9.5,
        },

        long_short_ratio_data={
            "ratio":
                0.55,
        },

        social_data={
            "score":
                -0.72,

            "sample_size":
                8000,
        },

        liquidation_data={
            "long_liquidations":
                5_000_000,

            "short_liquidations":
                900_000,
        },

        market_activity_data={
            "price_change_pct":
                -5.0,
        },
    )

    agent = SentimentAgent()

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SUCCESS
    ):

        print(
            "RESULT: FAIL - "
            "Expected SUCCESS."
        )

        return False

    if (
        output.bias
        !=
        TradeBias.SHORT
    ):

        print(
            "RESULT: FAIL - "
            "Expected SHORT bias."
        )

        return False

    if (
        output.regime
        not in (
            SentimentRegime.BEARISH,
            SentimentRegime.EXTREME_BEARISH,
        )
    ):

        print(
            "RESULT: FAIL - "
            "Expected bearish regime."
        )

        return False

    if (
        output.crowding_side
        !=
        CrowdingSide.SHORT
    ):

        print(
            "RESULT: FAIL - "
            "Expected SHORT crowding."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_neutral_market(
) -> bool:
    """
    TEST 3

    接近中性的市場。

    預期：

    - SUCCESS
    - NEUTRAL
    """

    print_separator(
        "TEST 3 - NEUTRAL MARKET"
    )

    context = (
        build_context()
    )

    payload = SentimentInput(
        funding_rate_data={
            "funding_rate":
                0.00001,
        },

        open_interest_data={
            "change_pct":
                0.5,
        },

        long_short_ratio_data={
            "ratio":
                1.01,
        },

        social_data={
            "score":
                0.02,

            "sample_size":
                2500,
        },

        liquidation_data={
            "long_liquidations":
                1_000_000,

            "short_liquidations":
                1_050_000,
        },

        market_activity_data={
            "price_change_pct":
                0.15,
        },
    )

    agent = SentimentAgent()

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_output(
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
        TradeBias.NEUTRAL
    ):

        print(
            "RESULT: FAIL - "
            "Expected NEUTRAL bias."
        )

        return False

    if (
        output.regime
        !=
        SentimentRegime.NEUTRAL
    ):

        print(
            "RESULT: FAIL - "
            "Expected NEUTRAL regime."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_disagreement(
) -> bool:
    """
    TEST 4

    故意建立互相衝突的 signals。

    - funding bullish
    - long/short bullish
    - social bearish
    - price bearish
    - liquidation bearish

    驗證 disagreement 有被計算。
    """

    print_separator(
        "TEST 4 - SIGNAL DISAGREEMENT"
    )

    context = (
        build_context()
    )

    payload = SentimentInput(
        funding_rate_data={
            "funding_rate":
                0.00080,
        },

        open_interest_data={
            "change_pct":
                7.0,
        },

        long_short_ratio_data={
            "ratio":
                1.50,
        },

        social_data={
            "score":
                -0.80,

            "sample_size":
                15000,
        },

        liquidation_data={
            "long_liquidations":
                4_000_000,

            "short_liquidations":
                1_000_000,
        },

        market_activity_data={
            "price_change_pct":
                -4.0,
        },
    )

    agent = SentimentAgent()

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_output(
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
        output.metrics
        .disagreement_score
        <= 0.10
    ):

        print(
            "RESULT: FAIL - "
            "Expected disagreement > 0.10."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_empty_input(
) -> bool:
    """
    TEST 5

    完全沒有 sentiment 資料。

    預期：

    SKIPPED

    而不是：

    ERROR
    """

    print_separator(
        "TEST 5 - EMPTY INPUT"
    )

    context = (
        build_context()
    )

    payload = (
        SentimentInput()
    )

    agent = SentimentAgent()

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_output(
        output
    )

    if (
        output.status
        !=
        AgentStatus.SKIPPED
    ):

        print(
            "RESULT: FAIL - "
            "Expected SKIPPED."
        )

        return False

    if (
        output.bias
        !=
        TradeBias.NEUTRAL
    ):

        print(
            "RESULT: FAIL - "
            "Empty input should "
            "remain NEUTRAL."
        )

        return False

    if (
        output.metrics.signal_count
        != 0
    ):

        print(
            "RESULT: FAIL - "
            "Expected zero signals."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_partial_data(
) -> bool:
    """
    TEST 6

    只有 funding。

    驗證 Agent 能處理 partial data，
    但 data quality / confidence
    應低於完整資料。
    """

    print_separator(
        "TEST 6 - PARTIAL DATA"
    )

    context = (
        build_context()
    )

    payload = SentimentInput(
        funding_rate_data={
            "funding_rate":
                0.00070,
        },
    )

    agent = SentimentAgent()

    output = (
        await agent.analyze(
            context=context,
            payload=payload,
        )
    )

    print_output(
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
        output.metrics.signal_count
        != 1
    ):

        print(
            "RESULT: FAIL - "
            "Expected one signal."
        )

        return False

    if (
        output.metrics
        .data_quality_score
        >= 0.50
    ):

        print(
            "RESULT: FAIL - "
            "Partial input should "
            "have limited data quality."
        )

        return False

    if (
        output.confidence
        >= 0.80
    ):

        print(
            "RESULT: FAIL - "
            "Single signal confidence "
            "should be reduced."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


def test_analyzer_directly(
) -> bool:
    """
    TEST 7

    不經過 Agent，
    直接確認 SentimentAnalyzer
    能輸出 SentimentSnapshot。
    """

    print_separator(
        "TEST 7 - ANALYZER DIRECT"
    )

    analyzer = (
        SentimentAnalyzer()
    )

    payload = SentimentInput(
        funding_rate_data={
            "funding_rate":
                0.00050,
        },

        long_short_ratio_data={
            "ratio":
                1.35,
        },

        market_activity_data={
            "price_change_pct":
                2.5,
        },

        open_interest_data={
            "change_pct":
                5.5,
        },
    )

    snapshot = (
        analyzer.analyze(
            symbol=(
                "BTC-USDT-SWAP"
            ),

            payload=payload,
        )
    )

    print(
        f"Symbol       : "
        f"{snapshot.symbol}"
    )

    print(
        f"Regime       : "
        f"{snapshot.regime.value}"
    )

    print(
        f"Crowding     : "
        f"{snapshot.crowding_side.value}"
    )

    print(
        f"Composite    : "
        f"{snapshot.metrics.composite_score:+.4f}"
    )

    print(
        f"Signal Count : "
        f"{snapshot.metrics.signal_count}"
    )

    if (
        snapshot.symbol
        !=
        "BTC-USDT-SWAP"
    ):

        print(
            "RESULT: FAIL"
        )

        return False

    if not snapshot.signals:

        print(
            "RESULT: FAIL - "
            "No signals generated."
        )

        return False

    if (
        snapshot.metrics.signal_count
        !=
        len(
            snapshot.signals
        )
    ):

        print(
            "RESULT: FAIL - "
            "Signal count mismatch."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def main(
) -> int:

    print_separator(
        "CODEX BOT - SENTIMENT AGENT TEST"
    )

    print(
        "Testing SENTIMENT pipeline:"
    )

    print()

    print(
        "Raw Sentiment Data"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentAnalyzer"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentSnapshot"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentAgent"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentOutput"
    )

    results: list[
        bool
    ] = []

    results.append(
        await test_bullish_crowded()
    )

    results.append(
        await test_bearish_crowded()
    )

    results.append(
        await test_neutral_market()
    )

    results.append(
        await test_disagreement()
    )

    results.append(
        await test_empty_input()
    )

    results.append(
        await test_partial_data()
    )

    results.append(
        test_analyzer_directly()
    )

    print_separator(
        "SENTIMENT TEST SUMMARY"
    )

    passed = sum(
        1
        for result
        in results
        if result
    )

    total = len(
        results
    )

    print(
        f"Passed: "
        f"{passed}/{total}"
    )

    if all(
        results
    ):

        print(
            "SENTIMENT TEST RESULT: PASS"
        )

        return 0

    print(
        "SENTIMENT TEST RESULT: FAIL"
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
            "SENTIMENT test interrupted."
        )

        raise SystemExit(
            130
        )
