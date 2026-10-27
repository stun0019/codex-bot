from __future__ import annotations

import asyncio
import math

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

from app.agents.charts import (
    CandleData,
    ChartsAgent,
    ChartsAnalyzer,
    ChartsInput,
    TechnicalIndicators,
    TrendRegime,
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
                "test_charts.py",
        },
    )


def build_candles(
    mode: str,
    count: int = 260,
    start_price: float = 100.0,
    step: float = 0.30,
    confirmed: bool = True,
) -> list[
    CandleData
]:
    """
    建立 deterministic candle data。

    mode:

        up
        down
        flat
        volatile
    """

    if count <= 0:

        return []

    start_time = (
        datetime.now(
            timezone.utc
        )
        -
        timedelta(
            hours=count
        )
    )

    candles: list[
        CandleData
    ] = []

    previous_close = (
        start_price
    )

    for index in range(
        count
    ):

        if mode == "up":

            trend = (
                start_price
                +
                step
                *
                index
            )

            oscillation = (
                math.sin(
                    index / 5.0
                )
                *
                0.25
            )

            close = (
                trend
                +
                oscillation
            )

        elif mode == "down":

            trend = (
                start_price
                -
                step
                *
                index
            )

            # 避免測試價格 <= 0
            trend = max(
                10.0,
                trend,
            )

            oscillation = (
                math.sin(
                    index / 5.0
                )
                *
                0.25
            )

            close = (
                trend
                +
                oscillation
            )

        elif mode == "flat":

            close = (
                start_price
            )

        elif mode == "volatile":

            close = (
                start_price
                +
                math.sin(
                    index / 2.0
                )
                *
                5.0
                +
                math.sin(
                    index / 7.0
                )
                *
                2.0
            )

        else:

            raise ValueError(
                (
                    "Unsupported candle "
                    f"mode: {mode}"
                )
            )

        close = max(
            1.0,
            close,
        )

        open_price = (
            previous_close
        )

        wick = (
            0.30
            if mode
            !=
            "volatile"
            else
            1.50
        )

        high = (
            max(
                open_price,
                close,
            )
            +
            wick
        )

        low = (
            min(
                open_price,
                close,
            )
            -
            wick
        )

        low = max(
            0.01,
            low,
        )

        volume = (
            1000.0
            +
            (
                index
                %
                17
            )
            *
            10.0
        )

        # 最後一段略微提高成交量，
        # 讓 volume confirmation
        # 有足夠測試資料。
        if (
            index
            >=
            count - 10
        ):

            volume *= (
                1.30
            )

        candles.append(
            CandleData(
                timestamp=(
                    start_time
                    +
                    timedelta(
                        hours=index
                    )
                ),

                open=(
                    open_price
                ),

                high=high,

                low=low,

                close=close,

                volume=volume,

                volume_currency=(
                    volume
                ),

                volume_quote=(
                    volume
                    *
                    close
                ),

                confirmed=(
                    confirmed
                ),

                metadata={
                    "test":
                        True,

                    "mode":
                        mode,
                },
            )
        )

        previous_close = (
            close
        )

    return candles


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
        f"Composite    : "
        f"{output.composite_score:+.4f}"
    )

    print(
        f"Trend        : "
        f"{output.trend_regime.value}"
    )

    print(
        f"Volatility   : "
        f"{output.volatility_regime.value}"
    )

    print(
        f"Primary TF   : "
        f"{output.primary_timeframe}"
    )

    print(
        f"Data Quality : "
        f"{output.data_quality_score:.4f}"
    )

    print(
        f"Disagreement : "
        f"{output.disagreement_score:.4f}"
    )

    print(
        f"Signals      : "
        f"{len(output.signals)}"
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
        timeframe,
        analysis,
    ) in (
        output
        .timeframe_analyses
        .items()
    ):

        print(
            f"[{timeframe}]"
        )

        print(
            f"  Bias       : "
            f"{analysis.bias.value}"
        )

        print(
            f"  Score      : "
            f"{analysis.score:+.4f}"
        )

        print(
            f"  Confidence : "
            f"{analysis.confidence:.4f}"
        )

        print(
            f"  Trend      : "
            f"{analysis.trend_regime.value}"
        )

        print(
            f"  Volatility : "
            f"{analysis.volatility_regime.value}"
        )

        print(
            f"  Candles    : "
            f"{analysis.candle_count}"
        )

        print(
            f"  Signals    : "
            f"{len(analysis.signals)}"
        )

        print()


def test_indicators(
) -> bool:

    print_separator(
        "TEST 1 - TECHNICAL INDICATORS"
    )

    candles = build_candles(
        mode="up",
        count=260,
    )

    indicators = (
        TechnicalIndicators()
    )

    result = (
        indicators.calculate(
            candles
        )
    )

    ema20 = (
        result[
            "ema"
        ][
            "20"
        ][
            "value"
        ]
    )

    ema50 = (
        result[
            "ema"
        ][
            "50"
        ][
            "value"
        ]
    )

    ema200 = (
        result[
            "ema"
        ][
            "200"
        ][
            "value"
        ]
    )

    rsi = (
        result[
            "rsi"
        ][
            "value"
        ]
    )

    macd = (
        result[
            "macd"
        ][
            "value"
        ]
    )

    atr = (
        result[
            "atr"
        ][
            "value"
        ]
    )

    upper = (
        result[
            "bollinger"
        ][
            "upper"
        ]
    )

    lower = (
        result[
            "bollinger"
        ][
            "lower"
        ]
    )

    print(
        f"EMA20  : {ema20}"
    )

    print(
        f"EMA50  : {ema50}"
    )

    print(
        f"EMA200 : {ema200}"
    )

    print(
        f"RSI    : {rsi}"
    )

    print(
        f"MACD   : {macd}"
    )

    print(
        f"ATR    : {atr}"
    )

    print(
        f"BB Up  : {upper}"
    )

    print(
        f"BB Low : {lower}"
    )

    if (
        ema20 is None
        or ema50 is None
        or ema200 is None
    ):

        print(
            "RESULT: FAIL - "
            "EMA values missing."
        )

        return False

    if not (
        ema20
        >
        ema50
        >
        ema200
    ):

        print(
            "RESULT: FAIL - "
            "Expected bullish "
            "EMA alignment."
        )

        return False

    if rsi is None:

        print(
            "RESULT: FAIL - "
            "RSI missing."
        )

        return False

    if macd is None:

        print(
            "RESULT: FAIL - "
            "MACD missing."
        )

        return False

    if (
        atr is None
        or atr <= 0
    ):

        print(
            "RESULT: FAIL - "
            "ATR invalid."
        )

        return False

    if (
        upper is None
        or lower is None
        or upper <= lower
    ):

        print(
            "RESULT: FAIL - "
            "Bollinger bands invalid."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_bullish_market(
) -> bool:

    print_separator(
        "TEST 2 - BULLISH MULTI-TIMEFRAME"
    )

    payload = ChartsInput(
        candles={
            "15m":
                build_candles(
                    "up",
                    260,
                    100.0,
                    0.20,
                ),

            "1H":
                build_candles(
                    "up",
                    260,
                    100.0,
                    0.28,
                ),

            "4H":
                build_candles(
                    "up",
                    260,
                    100.0,
                    0.35,
                ),
        }
    )

    output = (
        await ChartsAgent()
        .analyze(
            context=(
                build_context()
            ),
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
            "Expected LONG."
        )

        return False

    if (
        output.composite_score
        <= 0
    ):

        print(
            "RESULT: FAIL - "
            "Expected positive score."
        )

        return False

    if (
        output.trend_regime
        not in (
            TrendRegime.UPTREND,
            TrendRegime.STRONG_UPTREND,
        )
    ):

        print(
            "RESULT: FAIL - "
            "Expected uptrend."
        )

        return False

    if (
        len(
            output
            .timeframe_analyses
        )
        != 3
    ):

        print(
            "RESULT: FAIL - "
            "Expected 3 timeframes."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_bearish_market(
) -> bool:

    print_separator(
        "TEST 3 - BEARISH MULTI-TIMEFRAME"
    )

    payload = ChartsInput(
        candles={
            "15m":
                build_candles(
                    "down",
                    260,
                    200.0,
                    0.20,
                ),

            "1H":
                build_candles(
                    "down",
                    260,
                    220.0,
                    0.28,
                ),

            "4H":
                build_candles(
                    "down",
                    260,
                    240.0,
                    0.35,
                ),
        }
    )

    output = (
        await ChartsAgent()
        .analyze(
            context=(
                build_context(
                    "ETH-USDT-SWAP"
                )
            ),
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

        return False

    if (
        output.bias
        !=
        TradeBias.SHORT
    ):

        print(
            "RESULT: FAIL - "
            "Expected SHORT."
        )

        return False

    if (
        output.composite_score
        >= 0
    ):

        print(
            "RESULT: FAIL - "
            "Expected negative score."
        )

        return False

    if (
        output.trend_regime
        not in (
            TrendRegime.DOWNTREND,
            TrendRegime.STRONG_DOWNTREND,
        )
    ):

        print(
            "RESULT: FAIL - "
            "Expected downtrend."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_neutral_market(
) -> bool:

    print_separator(
        "TEST 4 - NEUTRAL MARKET"
    )

    payload = ChartsInput(
        candles={
            "1H":
                build_candles(
                    "flat",
                    260,
                    100.0,
                ),

            "4H":
                build_candles(
                    "flat",
                    260,
                    100.0,
                ),
        }
    )

    output = (
        await ChartsAgent()
        .analyze(
            context=(
                build_context()
            ),
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

        return False

    if (
        output.bias
        !=
        TradeBias.NEUTRAL
    ):

        print(
            "RESULT: FAIL - "
            "Expected NEUTRAL."
        )

        return False

    if (
        abs(
            output
            .composite_score
        )
        >= 0.18
    ):

        print(
            "RESULT: FAIL - "
            "Neutral market score "
            "too directional."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_timeframe_disagreement(
) -> bool:

    print_separator(
        "TEST 5 - TIMEFRAME DISAGREEMENT"
    )

    payload = ChartsInput(
        candles={
            "15m":
                build_candles(
                    "up",
                    260,
                    100.0,
                    0.30,
                ),

            "1H":
                build_candles(
                    "up",
                    260,
                    100.0,
                    0.20,
                ),

            "4H":
                build_candles(
                    "down",
                    260,
                    220.0,
                    0.35,
                ),
        }
    )

    analyzer = (
        ChartsAnalyzer()
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
        f"Composite    : "
        f"{snapshot.composite_score:+.4f}"
    )

    print(
        f"Disagreement : "
        f"{snapshot.disagreement_score:.4f}"
    )

    for (
        timeframe,
        analysis,
    ) in (
        snapshot
        .timeframe_analyses
        .items()
    ):

        print(
            f"{timeframe}: "
            f"{analysis.bias.value} "
            f"{analysis.score:+.4f}"
        )

    if (
        snapshot
        .disagreement_score
        <= 0.05
    ):

        print(
            "RESULT: FAIL - "
            "Expected timeframe "
            "disagreement."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_partial_history(
) -> bool:

    print_separator(
        "TEST 6 - PARTIAL HISTORY"
    )

    payload = ChartsInput(
        candles={
            "1H":
                build_candles(
                    "up",
                    30,
                    100.0,
                    0.25,
                ),
        }
    )

    output = (
        await ChartsAgent()
        .analyze(
            context=(
                build_context()
            ),
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
            "Partial chart history "
            "should still be usable."
        )

        return False

    if (
        output
        .data_quality_score
        >= 0.70
    ):

        print(
            "RESULT: FAIL - "
            "Expected reduced "
            "data quality."
        )

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_empty_input(
) -> bool:

    print_separator(
        "TEST 7 - EMPTY INPUT"
    )

    output = (
        await ChartsAgent()
        .analyze(
            context=(
                build_context()
            ),
            payload=(
                ChartsInput()
            ),
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

        return False

    if output.signals:

        return False

    print(
        "RESULT: PASS"
    )

    return True


async def test_unconfirmed_only(
) -> bool:

    print_separator(
        "TEST 8 - UNCONFIRMED ONLY"
    )

    payload = ChartsInput(
        candles={
            "1H":
                build_candles(
                    "up",
                    260,
                    confirmed=False,
                ),
        }
    )

    output = (
        await ChartsAgent()
        .analyze(
            context=(
                build_context()
            ),
            payload=payload,
        )
    )

    print_output(
        output
    )

    # ChartsAnalyzer 預設：
    # use_unconfirmed_candles=False
    #
    # 所以全部未確認的 candles
    # 應該被排除。
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

    print(
        "RESULT: PASS"
    )

    return True


async def main(
) -> int:

    print_separator(
        "CODEX BOT - CHARTS AGENT TEST"
    )

    print(
        "Testing:"
    )

    print()

    print(
        "Candles"
    )

    print(
        "   ↓"
    )

    print(
        "TechnicalIndicators"
    )

    print(
        "   ↓"
    )

    print(
        "ChartsAnalyzer"
    )

    print(
        "   ↓"
    )

    print(
        "ChartsAgent"
    )

    print(
        "   ↓"
    )

    print(
        "ChartsOutput"
    )

    results: list[
        bool
    ] = []

    results.append(
        test_indicators()
    )

    results.append(
        await test_bullish_market()
    )

    results.append(
        await test_bearish_market()
    )

    results.append(
        await test_neutral_market()
    )

    results.append(
        await test_timeframe_disagreement()
    )

    results.append(
        await test_partial_history()
    )

    results.append(
        await test_empty_input()
    )

    results.append(
        await test_unconfirmed_only()
    )

    print_separator(
        "CHARTS TEST SUMMARY"
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
            "CHARTS TEST RESULT: PASS"
        )

        return 0

    print(
        "CHARTS TEST RESULT: FAIL"
    )

    return 1


if __name__ == "__main__":

    try:

        raise SystemExit(
            asyncio.run(
                main()
            )
        )

    except KeyboardInterrupt:

        print()

        print(
            "CHARTS test interrupted."
        )

        raise SystemExit(
            130
        )
