from __future__ import annotations

import asyncio
import math
import os

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from typing import Any

from app.agents.models import (
    AgentStatus,
    MarketContext,
    TradeBias,
)

from app.agents.charts import (
    BaseChartsSource,
    CandleData,
    ChartsInput,
    ChartsService,
    ChartsServiceConfig,
    ChartsSourceConfig,
    ChartsSourceResult,
    OKXChartsSource,
    OKXChartsSourceConfig,
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

        market_data={
            "test_context":
                True,
        },

        metadata={
            "test":
                True,

            "source":
                "test_charts_pipeline.py",
        },
    )


def build_candles(
    mode: str,
    count: int = 260,
    start_price: float = 100.0,
    step: float = 0.30,
) -> list[
    CandleData
]:

    start_time = (
        datetime.now(
            timezone.utc
        )
        -
        timedelta(
            hours=count
        )
    )

    result: list[
        CandleData
    ] = []

    previous_close = (
        start_price
    )

    for index in range(
        count
    ):

        if mode == "up":

            close = (
                start_price
                +
                step
                *
                index
                +
                math.sin(
                    index / 5.0
                )
                *
                0.20
            )

        elif mode == "down":

            close = (
                start_price
                -
                step
                *
                index
                +
                math.sin(
                    index / 5.0
                )
                *
                0.20
            )

            close = max(
                5.0,
                close,
            )

        elif mode == "flat":

            close = (
                start_price
            )

        else:

            raise ValueError(
                (
                    "Unsupported mode: "
                    f"{mode}"
                )
            )

        open_price = (
            previous_close
        )

        high = (
            max(
                open_price,
                close,
            )
            +
            0.30
        )

        low = (
            max(
                0.01,
                min(
                    open_price,
                    close,
                )
                -
                0.30
            )
        )

        volume = (
            1000.0
            +
            (
                index
                %
                11
            )
            *
            15.0
        )

        if (
            index
            >=
            count - 10
        ):

            volume *= 1.30

        result.append(
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

                confirmed=True,

                metadata={
                    "test":
                        True,
                },
            )
        )

        previous_close = (
            close
        )

    return result


class FakeChartsSource(
    BaseChartsSource
):
    """
    ChartsService 測試 source。

    可模擬：

        success
        no data
        source exception
        partial source errors
        merge conflict
    """

    def __init__(
        self,
        name: str,
        payload: (
            ChartsInput
            | None
        ) = None,
        fail: bool = False,
        errors: (
            list[str]
            | None
        ) = None,
        metadata: (
            dict[
                str,
                Any,
            ]
            | None
        ) = None,
    ) -> None:

        super().__init__(
            ChartsSourceConfig(
                name=name,
            )
        )

        self.payload = (
            payload
            if payload is not None
            else ChartsInput()
        )

        self.fail = (
            fail
        )

        self.result_errors = (
            list(
                errors
            )
            if errors is not None
            else []
        )

        self.result_metadata = (
            dict(
                metadata
            )
            if metadata is not None
            else {}
        )

    async def fetch(
        self,
        context: MarketContext,
    ) -> ChartsSourceResult:

        self.ensure_available()

        if self.fail:

            raise RuntimeError(
                "Fake charts source "
                "failure."
            )

        return ChartsSourceResult(
            source=self.name,

            payload=(
                self.payload
                .model_copy(
                    deep=True
                )
            ),

            errors=list(
                self.result_errors
            ),

            metadata={
                "fake":
                    True,

                "symbol":
                    context.symbol,

                **self.result_metadata,
            },
        )


async def test_service_success(
) -> bool:

    print_separator(
        "TEST 1 - CHARTS SERVICE SUCCESS"
    )

    source = FakeChartsSource(
        name="primary",

        payload=(
            ChartsInput(
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
                            0.25,
                        ),

                    "4H":
                        build_candles(
                            "up",
                            260,
                            100.0,
                            0.30,
                        ),
                }
            )
        ),
    )

    service = ChartsService(
        sources=[
            source
        ]
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context()
                )
            )
        )

        print(
            f"Status          : "
            f"{output.status.value}"
        )

        print(
            f"Bias            : "
            f"{output.bias.value}"
        )

        print(
            f"Composite       : "
            f"{output.composite_score:+.4f}"
        )

        print(
            f"Sources         : "
            f"{output.data.get('sources_succeeded')}/"
            f"{output.data.get('sources_requested')}"
        )

        print(
            f"Sources w/data  : "
            f"{output.data.get('sources_with_data')}"
        )

        print(
            f"Timeframes      : "
            f"{output.data.get('timeframes_merged')}"
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
            output.data.get(
                "sources_requested"
            )
            != 1
        ):

            return False

        if (
            output.data.get(
                "sources_succeeded"
            )
            != 1
        ):

            return False

        if (
            output.data.get(
                "sources_with_data"
            )
            != 1
        ):

            return False

        if (
            len(
                output
                .timeframe_analyses
            )
            != 3
        ):

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_multiple_sources(
) -> bool:

    print_separator(
        "TEST 2 - MULTIPLE SOURCES"
    )

    source_a = FakeChartsSource(
        name="short_tf",

        payload=(
            ChartsInput(
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
                            0.25,
                        ),
                }
            )
        ),
    )

    source_b = FakeChartsSource(
        name="long_tf",

        payload=(
            ChartsInput(
                candles={
                    "4H":
                        build_candles(
                            "up",
                            260,
                            100.0,
                            0.35,
                        ),
                }
            )
        ),
    )

    service = ChartsService(
        sources=[
            source_a,
            source_b,
        ]
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context()
                )
            )
        )

        print(
            f"Sources requested : "
            f"{output.data.get('sources_requested')}"
        )

        print(
            f"Sources succeeded : "
            f"{output.data.get('sources_succeeded')}"
        )

        print(
            f"Timeframe sources : "
            f"{output.data.get('timeframe_sources')}"
        )

        if (
            output.status
            !=
            AgentStatus.SUCCESS
        ):

            return False

        if (
            output.data.get(
                "sources_succeeded"
            )
            != 2
        ):

            print(
                "RESULT: FAIL - "
                "Expected 2 sources."
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
                "Expected 3 merged "
                "timeframes."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_partial_failure(
) -> bool:

    print_separator(
        "TEST 3 - PARTIAL SOURCE FAILURE"
    )

    good = FakeChartsSource(
        name="good",

        payload=(
            ChartsInput(
                candles={
                    "1H":
                        build_candles(
                            "up",
                            260,
                        ),

                    "4H":
                        build_candles(
                            "up",
                            260,
                        ),
                }
            )
        ),
    )

    broken = FakeChartsSource(
        name="broken",
        fail=True,
    )

    service = ChartsService(
        sources=[
            good,
            broken,
        ]
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context()
                )
            )
        )

        print(
            f"Status            : "
            f"{output.status.value}"
        )

        print(
            f"Sources succeeded : "
            f"{output.data.get('sources_succeeded')}"
        )

        print(
            f"Source errors     : "
            f"{output.data.get('source_errors')}"
        )

        if (
            output.status
            ==
            AgentStatus.ERROR
        ):

            print(
                "RESULT: FAIL - "
                "Partial source failure "
                "must not kill pipeline."
            )

            return False

        if (
            output.data.get(
                "sources_requested"
            )
            != 2
        ):

            return False

        if (
            output.data.get(
                "sources_succeeded"
            )
            != 1
        ):

            return False

        if not (
            output.data.get(
                "source_errors"
            )
        ):

            print(
                "RESULT: FAIL - "
                "Expected source error."
            )

            return False

        if not output.errors:

            print(
                "RESULT: FAIL - "
                "Error not propagated."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_empty_source(
) -> bool:

    print_separator(
        "TEST 4 - EMPTY SOURCE"
    )

    source = FakeChartsSource(
        name="empty",
        payload=(
            ChartsInput()
        ),
    )

    service = ChartsService(
        sources=[
            source
        ]
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context()
                )
            )
        )

        print(
            f"Status           : "
            f"{output.status.value}"
        )

        print(
            f"Sources succeeded: "
            f"{output.data.get('sources_succeeded')}"
        )

        print(
            f"Sources w/data   : "
            f"{output.data.get('sources_with_data')}"
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
            output.data.get(
                "sources_succeeded"
            )
            != 1
        ):

            return False

        if (
            output.data.get(
                "sources_with_data"
            )
            != 0
        ):

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_merge_conflict(
) -> bool:

    print_separator(
        "TEST 5 - TIMEFRAME MERGE CONFLICT"
    )

    first = FakeChartsSource(
        name="first",

        payload=(
            ChartsInput(
                candles={
                    "1H":
                        build_candles(
                            "up",
                            260,
                            100.0,
                            0.30,
                        ),
                }
            )
        ),
    )

    second = FakeChartsSource(
        name="second",

        payload=(
            ChartsInput(
                candles={
                    "1H":
                        build_candles(
                            "down",
                            260,
                            220.0,
                            0.30,
                        ),
                }
            )
        ),
    )

    service = ChartsService(
        sources=[
            first,
            second,
        ],

        config=(
            ChartsServiceConfig(
                preserve_first_timeframe_on_conflict=True,
            )
        ),
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context()
                )
            )
        )

        conflict_count = (
            output.data.get(
                "merge_conflict_count",
                0,
            )
        )

        timeframe_sources = (
            output.data.get(
                "timeframe_sources",
                {},
            )
        )

        print(
            f"Conflicts        : "
            f"{conflict_count}"
        )

        print(
            f"Timeframe source : "
            f"{timeframe_sources}"
        )

        if conflict_count < 1:

            print(
                "RESULT: FAIL - "
                "Expected conflict."
            )

            return False

        if (
            timeframe_sources.get(
                "1H"
            )
            !=
            "first"
        ):

            print(
                "RESULT: FAIL - "
                "First source was not "
                "preserved."
            )

            return False

        analysis = (
            output
            .timeframe_analyses
            .get(
                "1H"
            )
        )

        if analysis is None:

            return False

        if (
            analysis.bias
            !=
            TradeBias.LONG
        ):

            print(
                "RESULT: FAIL - "
                "Expected first source's "
                "bullish candles."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_source_internal_errors(
) -> bool:

    print_separator(
        "TEST 6 - SOURCE INTERNAL ERROR"
    )

    source = FakeChartsSource(
        name="partial",

        payload=(
            ChartsInput(
                candles={
                    "1H":
                        build_candles(
                            "up",
                            260,
                        ),
                }
            )
        ),

        errors=[
            (
                "4H: fake timeframe "
                "endpoint failure"
            )
        ],
    )

    service = ChartsService(
        sources=[
            source
        ]
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context()
                )
            )
        )

        print(
            f"Status : "
            f"{output.status.value}"
        )

        print(
            f"Errors : "
            f"{output.errors}"
        )

        if (
            output.status
            ==
            AgentStatus.ERROR
        ):

            print(
                "RESULT: FAIL - "
                "Partial timeframe error "
                "must not kill pipeline."
            )

            return False

        if (
            output.data.get(
                "sources_with_data"
            )
            != 1
        ):

            return False

        if not output.errors:

            print(
                "RESULT: FAIL - "
                "Expected partial error."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_live_okx(
) -> bool:
    """
    真實 OKX public candle pipeline。

    預設不跑。

    Windows CMD:

        set RUN_LIVE_CHARTS_OKX=1
        python backend/test_charts_pipeline.py

    PowerShell:

        $env:RUN_LIVE_CHARTS_OKX="1"
        python backend/test_charts_pipeline.py
    """

    print_separator(
        "TEST 7 - LIVE OKX CHARTS"
    )

    if (
        os.getenv(
            "RUN_LIVE_CHARTS_OKX",
            "",
        ).strip()
        !=
        "1"
    ):

        print(
            "SKIPPED"
        )

        print(
            "Set "
            "RUN_LIVE_CHARTS_OKX=1 "
            "to enable."
        )

        return True

    source = OKXChartsSource(
        config=(
            OKXChartsSourceConfig(
                default_timeframes=[
                    "15m",
                    "1H",
                    "4H",
                ],

                candle_limit=300,

                use_context_timeframes=True,

                include_unconfirmed=True,

                timeout_seconds=15.0,

                max_retries=3,
            )
        )
    )

    service = ChartsService(
        sources=[
            source
        ],

        config=(
            ChartsServiceConfig(
                source_timeout_seconds=45.0,
            )
        ),
    )

    try:

        output = (
            await service.analyze(
                context=(
                    build_context(
                        "BTC-USDT-SWAP"
                    )
                )
            )
        )

        print(
            f"Status          : "
            f"{output.status.value}"
        )

        print(
            f"Bias            : "
            f"{output.bias.value}"
        )

        print(
            f"Confidence      : "
            f"{output.confidence:.4f}"
        )

        print(
            f"Composite       : "
            f"{output.composite_score:+.4f}"
        )

        print(
            f"Trend           : "
            f"{output.trend_regime.value}"
        )

        print(
            f"Volatility      : "
            f"{output.volatility_regime.value}"
        )

        print(
            f"Primary TF      : "
            f"{output.primary_timeframe}"
        )

        print(
            f"Signals         : "
            f"{len(output.signals)}"
        )

        print(
            f"Sources         : "
            f"{output.data.get('sources_succeeded')}/"
            f"{output.data.get('sources_requested')}"
        )

        print(
            f"Sources w/data  : "
            f"{output.data.get('sources_with_data')}"
        )

        print(
            f"Timeframes      : "
            f"{output.data.get('timeframes_merged')}"
        )

        print()

        print(
            "Source status:"
        )

        for (
            source_name,
            status,
        ) in (
            output.data
            .get(
                "source_status",
                {},
            )
            .items()
        ):

            print(
                f"- {source_name}: "
                f"{status}"
            )

        print()

        print(
            "Timeframe analyses:"
        )

        for (
            timeframe,
            analysis,
        ) in (
            output
            .timeframe_analyses
            .items()
        ):

            print(
                (
                    f"- {timeframe}"
                    f" | "
                    f"bias="
                    f"{analysis.bias.value}"
                    f" | "
                    f"score="
                    f"{analysis.score:+.4f}"
                    f" | "
                    f"confidence="
                    f"{analysis.confidence:.4f}"
                    f" | "
                    f"candles="
                    f"{analysis.candle_count}"
                )
            )

        if output.errors:

            print()

            print(
                "Partial errors:"
            )

            for error in (
                output.errors
            ):

                print(
                    f"- {error}"
                )

        # Live test 允許其中某個
        # timeframe partial failure。
        #
        # 只要 OKX source 至少
        # 提供一個 timeframe，
        # pipeline 就算有可用資料。
        if (
            output.data.get(
                "sources_with_data"
            )
            != 1
        ):

            print(
                "RESULT: FAIL - "
                "OKX returned no "
                "usable candle data."
            )

            return False

        if not (
            output
            .timeframe_analyses
        ):

            print(
                "RESULT: FAIL - "
                "No timeframe analysis."
            )

            return False

        if (
            output.status
            ==
            AgentStatus.ERROR
        ):

            print(
                "RESULT: FAIL - "
                "ChartsAgent returned "
                "ERROR."
            )

            return False

        if not output.signals:

            print(
                "RESULT: FAIL - "
                "No technical signals."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def main(
) -> int:

    print_separator(
        "CODEX BOT - CHARTS PIPELINE TEST"
    )

    print(
        "Pipeline:"
    )

    print()

    print(
        "Charts Sources"
    )

    print(
        "    ↓"
    )

    print(
        "ChartsService"
    )

    print(
        "    ↓"
    )

    print(
        "ChartsInput"
    )

    print(
        "    ↓"
    )

    print(
        "TechnicalIndicators"
    )

    print(
        "    ↓"
    )

    print(
        "ChartsAnalyzer"
    )

    print(
        "    ↓"
    )

    print(
        "ChartsAgent"
    )

    print(
        "    ↓"
    )

    print(
        "ChartsOutput"
    )

    results: list[
        bool
    ] = []

    results.append(
        await test_service_success()
    )

    results.append(
        await test_multiple_sources()
    )

    results.append(
        await test_partial_failure()
    )

    results.append(
        await test_empty_source()
    )

    results.append(
        await test_merge_conflict()
    )

    results.append(
        await test_source_internal_errors()
    )

    results.append(
        await test_live_okx()
    )

    print_separator(
        "CHARTS PIPELINE SUMMARY"
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
            "CHARTS PIPELINE RESULT: PASS"
        )

        return 0

    print(
        "CHARTS PIPELINE RESULT: FAIL"
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
            "CHARTS pipeline "
            "test interrupted."
        )

        raise SystemExit(
            130
        )
