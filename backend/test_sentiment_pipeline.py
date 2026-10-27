from __future__ import annotations

import asyncio
import os

from typing import Any

from app.agents.models import (
    AgentStatus,
    MarketContext,
)

from app.agents.sentiment import (
    BaseSentimentSource,
    OKXSentimentSource,
    OKXSentimentSourceConfig,
    SentimentAgent,
    SentimentInput,
    SentimentService,
    SentimentServiceConfig,
    SentimentSourceConfig,
    SentimentSourceResult,
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
            "context_source":
                True,
        },

        metadata={
            "test":
                True,

            "source":
                "test_sentiment_pipeline.py",
        },
    )


class FakeSentimentSource(
    BaseSentimentSource
):
    """
    SENTIMENT Service 測試用 source。

    可模擬：

    - 正常資料
    - partial data
    - source failure
    - merge conflicts
    """

    def __init__(
        self,
        name: str,
        payload: SentimentInput | None = None,
        fail: bool = False,
        result_errors: (
            list[str]
            | None
        ) = None,
        metadata: (
            dict[str, Any]
            | None
        ) = None,
    ) -> None:

        super().__init__(
            SentimentSourceConfig(
                name=name,
            )
        )

        self.payload = (
            payload
            if payload is not None
            else SentimentInput()
        )

        self.fail = fail

        self.result_errors = (
            list(
                result_errors
            )
            if result_errors
            is not None
            else []
        )

        self.result_metadata = (
            dict(
                metadata
            )
            if metadata
            is not None
            else {}
        )

    async def fetch(
        self,
        context: MarketContext,
    ) -> SentimentSourceResult:

        self.ensure_available()

        if self.fail:

            raise RuntimeError(
                "Fake sentiment source "
                "failure."
            )

        return SentimentSourceResult(
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
    """
    TEST 1

    兩個正常 source。

    Source A：
        funding
        OI
        market activity

    Source B：
        long/short
        social
        liquidations

    預期：

        SUCCESS
        multiple signals
        2/2 sources succeeded
    """

    print_separator(
        "TEST 1 - SENTIMENT SERVICE SUCCESS"
    )

    source_a = (
        FakeSentimentSource(
            name="source_a",

            payload=(
                SentimentInput(
                    funding_rate_data={
                        "funding_rate":
                            0.00065,
                    },

                    open_interest_data={
                        "change_pct":
                            7.5,
                    },

                    market_activity_data={
                        "price_change_pct":
                            3.2,
                    },
                )
            ),
        )
    )

    source_b = (
        FakeSentimentSource(
            name="source_b",

            payload=(
                SentimentInput(
                    long_short_ratio_data={
                        "ratio":
                            1.42,
                    },

                    social_data={
                        "score":
                            0.55,

                        "sample_size":
                            5000,
                    },

                    liquidation_data={
                        "long_liquidations":
                            1_000_000,

                        "short_liquidations":
                            3_500_000,
                    },
                )
            ),
        )
    )

    service = SentimentService(
        agent=SentimentAgent(),

        sources=[
            source_a,
            source_b,
        ],

        config=(
            SentimentServiceConfig(
                include_context_market_data=False,
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

        print(
            f"Status: "
            f"{output.status.value}"
        )

        print(
            f"Bias: "
            f"{output.bias.value}"
        )

        print(
            f"Signals: "
            f"{output.metrics.signal_count}"
        )

        print(
            f"Sources: "
            f"{output.data.get('sources_succeeded')}/"
            f"{output.data.get('sources_requested')}"
        )

        print(
            f"Sources with data: "
            f"{output.data.get('sources_with_data')}"
        )

        print(
            f"Errors: "
            f"{output.errors}"
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
            output.data.get(
                "sources_requested"
            )
            != 2
        ):

            print(
                "RESULT: FAIL - "
                "Expected 2 requested sources."
            )

            return False

        if (
            output.data.get(
                "sources_succeeded"
            )
            != 2
        ):

            print(
                "RESULT: FAIL - "
                "Expected 2 successful sources."
            )

            return False

        if (
            output.data.get(
                "sources_with_data"
            )
            != 2
        ):

            print(
                "RESULT: FAIL - "
                "Expected 2 sources with data."
            )

            return False

        if (
            output.metrics
            .signal_count
            < 5
        ):

            print(
                "RESULT: FAIL - "
                "Expected multiple signals."
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
    """
    TEST 2

    一個 source 正常，
    一個 source 故意失敗。

    預期：

        整個 SENTIMENT pipeline
        仍可繼續。

        source failure 應存在：

            output.errors
            output.data["source_errors"]
    """

    print_separator(
        "TEST 2 - PARTIAL SOURCE FAILURE"
    )

    good_source = (
        FakeSentimentSource(
            name="good",

            payload=(
                SentimentInput(
                    funding_rate_data={
                        "funding_rate":
                            0.00050,
                    },

                    long_short_ratio_data={
                        "ratio":
                            1.30,
                    },

                    market_activity_data={
                        "price_change_pct":
                            2.0,
                    },
                )
            ),
        )
    )

    broken_source = (
        FakeSentimentSource(
            name="broken",
            fail=True,
        )
    )

    service = SentimentService(
        sources=[
            good_source,
            broken_source,
        ],

        config=(
            SentimentServiceConfig(
                include_context_market_data=False,
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

        print(
            f"Status: "
            f"{output.status.value}"
        )

        print(
            f"Sources succeeded: "
            f"{output.data.get('sources_succeeded')}"
        )

        print(
            f"Source errors: "
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

            print(
                "RESULT: FAIL - "
                "Expected exactly one "
                "successful source."
            )

            return False

        source_errors = (
            output.data.get(
                "source_errors"
            )
            or []
        )

        if not source_errors:

            print(
                "RESULT: FAIL - "
                "Expected source error."
            )

            return False

        if not output.errors:

            print(
                "RESULT: FAIL - "
                "Top-level errors should "
                "surface source failure."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_empty_sources(
) -> bool:
    """
    TEST 3

    Source 成功執行，
    但沒有 sentiment data。

    預期：

        Agent SKIPPED
    """

    print_separator(
        "TEST 3 - EMPTY SOURCE DATA"
    )

    source = (
        FakeSentimentSource(
            name="empty",
            payload=(
                SentimentInput()
            ),
        )
    )

    service = SentimentService(
        sources=[
            source
        ],

        config=(
            SentimentServiceConfig(
                include_context_market_data=False,
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

        print(
            f"Status: "
            f"{output.status.value}"
        )

        print(
            f"Sources succeeded: "
            f"{output.data.get('sources_succeeded')}"
        )

        print(
            f"Sources with data: "
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
    """
    TEST 4

    Source A 和 B 都提供
    funding_rate。

    預設：

        preserve_first_value_on_conflict=True

    預期：

        第一個 source 的 funding_rate
        被保留。

        conflict 被記錄。
    """

    print_separator(
        "TEST 4 - MERGE CONFLICT"
    )

    source_a = (
        FakeSentimentSource(
            name="first",

            payload=(
                SentimentInput(
                    funding_rate_data={
                        "funding_rate":
                            0.00020,

                        "source":
                            "first",
                    },

                    market_activity_data={
                        "price_change_pct":
                            1.5,
                    },
                )
            ),
        )
    )

    source_b = (
        FakeSentimentSource(
            name="second",

            payload=(
                SentimentInput(
                    funding_rate_data={
                        "funding_rate":
                            -0.00090,

                        "source":
                            "second",
                    },
                )
            ),
        )
    )

    service = SentimentService(
        sources=[
            source_a,
            source_b,
        ],

        config=(
            SentimentServiceConfig(
                preserve_first_value_on_conflict=True,

                include_context_market_data=False,
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

        conflicts = (
            output.data.get(
                "merge_conflicts",
                [],
            )
        )

        print(
            f"Conflict count: "
            f"{conflict_count}"
        )

        for conflict in conflicts:

            print(
                f"- "
                f"{conflict}"
            )

        if (
            conflict_count
            < 1
        ):

            print(
                "RESULT: FAIL - "
                "Expected merge conflict."
            )

            return False

        funding_signals = [
            signal
            for signal
            in output.signals
            if signal.name
            ==
            "funding_rate"
        ]

        if not funding_signals:

            print(
                "RESULT: FAIL - "
                "Funding signal missing."
            )

            return False

        funding_signal = (
            funding_signals[0]
        )

        if (
            funding_signal.value
            !=
            0.00020
        ):

            print(
                "RESULT: FAIL - "
                "First source value "
                "was not preserved."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_context_market_data_merge(
) -> bool:
    """
    TEST 5

    Context.market_data 可以補進
    market_activity_data。

    用來支援未來：

        SCOUT / market service
            ↓
        MarketContext
            ↓
        SENTIMENT

    不必重新抓所有資料。
    """

    print_separator(
        "TEST 5 - MARKET CONTEXT MERGE"
    )

    context = build_context()

    context.market_data = {
        "price_change_pct":
            -3.5,

        "context_marker":
            "present",
    }

    source = (
        FakeSentimentSource(
            name="funding_only",

            payload=(
                SentimentInput(
                    funding_rate_data={
                        "funding_rate":
                            -0.00040,
                    }
                )
            ),
        )
    )

    service = SentimentService(
        sources=[
            source
        ],

        config=(
            SentimentServiceConfig(
                include_context_market_data=True,
            )
        ),
    )

    try:

        output = (
            await service.analyze(
                context=context
            )
        )

        print(
            f"Status: "
            f"{output.status.value}"
        )

        print(
            f"Signal count: "
            f"{output.metrics.signal_count}"
        )

        market_activity_signals = [
            signal
            for signal
            in output.signals
            if signal.name
            ==
            "price_activity"
        ]

        if not (
            market_activity_signals
        ):

            print(
                "RESULT: FAIL - "
                "Context market data "
                "was not converted into "
                "market activity signal."
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
    """
    TEST 6

    Source 本身成功，
    但回傳 partial component errors。

    模擬：

        OKX Funding 成功
        Liquidation endpoint 失敗

    預期：

        source 本身仍算 succeeded
        pipeline 仍可分析
        error 被保留
    """

    print_separator(
        "TEST 6 - SOURCE INTERNAL ERRORS"
    )

    source = (
        FakeSentimentSource(
            name="partial",

            payload=(
                SentimentInput(
                    funding_rate_data={
                        "funding_rate":
                            0.00045,
                    },

                    market_activity_data={
                        "price_change_pct":
                            1.8,
                    },
                )
            ),

            result_errors=[
                (
                    "liquidations: "
                    "Fake endpoint error"
                )
            ],
        )
    )

    service = SentimentService(
        sources=[
            source
        ],

        config=(
            SentimentServiceConfig(
                include_context_market_data=False,
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

        print(
            f"Status: "
            f"{output.status.value}"
        )

        print(
            f"Errors: "
            f"{output.errors}"
        )

        if (
            output.status
            ==
            AgentStatus.ERROR
        ):

            print(
                "RESULT: FAIL - "
                "Internal partial error "
                "must not kill pipeline."
            )

            return False

        if (
            output.data.get(
                "sources_succeeded"
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
    TEST 7

    真實 OKX public sentiment pipeline。

    預設不執行。

    Windows CMD:

        set RUN_LIVE_SENTIMENT_OKX=1
        python backend/test_sentiment_pipeline.py

    PowerShell:

        $env:RUN_LIVE_SENTIMENT_OKX="1"
        python backend/test_sentiment_pipeline.py

    不需要 API Key。
    """

    print_separator(
        "TEST 7 - LIVE OKX SENTIMENT"
    )

    if (
        os.getenv(
            "RUN_LIVE_SENTIMENT_OKX",
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
            "RUN_LIVE_SENTIMENT_OKX=1 "
            "to enable."
        )

        return True

    source = OKXSentimentSource(
        config=(
            OKXSentimentSourceConfig(
                period="1H",

                include_funding=True,

                include_open_interest=True,

                include_long_short_ratio=True,

                include_market_activity=True,

                include_liquidations=True,
            )
        )
    )

    service = SentimentService(
        sources=[
            source
        ],

        config=(
            SentimentServiceConfig(
                source_timeout_seconds=30.0,

                include_context_market_data=False,
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
            f"Regime          : "
            f"{output.regime.value}"
        )

        print(
            f"Crowding        : "
            f"{output.crowding_side.value}"
        )

        print(
            f"Composite       : "
            f"{output.metrics.composite_score:+.4f}"
        )

        print(
            f"Signal count    : "
            f"{output.metrics.signal_count}"
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

        print()

        print(
            "Source status:"
        )

        source_status = (
            output.data.get(
                "source_status",
                {},
            )
        )

        for (
            source_name,
            status,
        ) in source_status.items():

            print(
                f"- {source_name}: "
                f"{status}"
            )

        print()

        if output.errors:

            print(
                "Partial errors:"
            )

            for error in (
                output.errors
            ):

                print(
                    f"- {error}"
                )

        print()

        print(
            "Signals:"
        )

        for signal in (
            output.signals
        ):

            print(
                (
                    f"- "
                    f"{signal.source.value}"
                    f" / "
                    f"{signal.name}"
                    f" | "
                    f"score="
                    f"{signal.score:+.4f}"
                    f" | "
                    f"confidence="
                    f"{signal.confidence:.4f}"
                    f" | "
                    f"crowding="
                    f"{signal.crowding_score:.4f}"
                )
            )

        # Live API 允許 partial failures。
        #
        # 只要至少抓到一種 sentiment
        # 資料，就視為 live source 正常。
        if (
            output.data.get(
                "sources_with_data"
            )
            != 1
        ):

            print(
                "RESULT: FAIL - "
                "OKX returned no usable "
                "sentiment data."
            )

            return False

        if (
            output.metrics
            .signal_count
            <= 0
        ):

            print(
                "RESULT: FAIL - "
                "No sentiment signals "
                "were generated."
            )

            return False

        if (
            output.status
            ==
            AgentStatus.ERROR
        ):

            print(
                "RESULT: FAIL - "
                "Agent returned ERROR."
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
        "CODEX BOT - SENTIMENT PIPELINE TEST"
    )

    print(
        "Pipeline:"
    )

    print()

    print(
        "Sentiment Sources"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentService"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentInput"
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
        "SentimentAgent"
    )

    print(
        "    ↓"
    )

    print(
        "SentimentOutput"
    )

    results = [
        await test_service_success(),
        await test_partial_failure(),
        await test_empty_sources(),
        await test_merge_conflict(),
        await test_context_market_data_merge(),
        await test_source_internal_errors(),
        await test_live_okx(),
    ]

    passed = sum(
        1
        for result
        in results
        if result
    )

    total = len(
        results
    )

    print_separator(
        "SENTIMENT PIPELINE SUMMARY"
    )

    print(
        f"Passed: "
        f"{passed}/{total}"
    )

    if all(
        results
    ):

        print(
            "SENTIMENT PIPELINE RESULT: PASS"
        )

        return 0

    print(
        "SENTIMENT PIPELINE RESULT: FAIL"
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
            "SENTIMENT pipeline "
            "test interrupted."
        )

        raise SystemExit(
            130
        )
