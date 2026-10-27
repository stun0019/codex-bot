from __future__ import annotations

import asyncio

from dataclasses import (
    dataclass,
)

from typing import Any

from ..models import (
    MarketContext,
)

from .agent import (
    SentimentAgent,
)

from .models import (
    SentimentInput,
    SentimentOutput,
    SentimentSignal,
)

from .sources import (
    BaseSentimentSource,
    OKXSentimentSource,
    SentimentSourceResult,
)


@dataclass(slots=True)
class SentimentServiceConfig:
    """
    SENTIMENT orchestration 設定。

    SentimentService 負責：

        Sources
            ↓
        SentimentInput
            ↓
        SentimentAgent
            ↓
        SentimentOutput

    Service 不負責：

        - 自己判斷 LONG / SHORT
        - 自己計算 composite score
        - trade execution
        - position sizing
        - stop loss
        - take profit
    """

    source_timeout_seconds: float = 20.0

    include_context_market_data: bool = True

    preserve_first_value_on_conflict: bool = True

    close_sources_on_close: bool = True

    def __post_init__(
        self,
    ) -> None:

        if (
            self.source_timeout_seconds
            <= 0
        ):

            raise ValueError(
                "source_timeout_seconds "
                "must be greater than 0."
            )


@dataclass(slots=True)
class _SourceExecutionResult:
    """
    Service 內部使用的 source
    執行結果。
    """

    source: BaseSentimentSource

    result: (
        SentimentSourceResult
        | None
    ) = None

    error: (
        Exception
        | None
    ) = None


class SentimentService:
    """
    SENTIMENT 完整 orchestration service。

    Pipeline:

        OKX / Social / Future Sources
                ↓
        concurrent source fetch
                ↓
        partial failure isolation
                ↓
        SentimentInput merge
                ↓
        SentimentAgent
                ↓
        SentimentOutput

    預設：

        OKXSentimentSource

    未來可以加入：

        SocialSentimentSource
        FearGreedSource
        CoinglassSource
        ExchangePositioningSource

    而不需要修改 SentimentAgent。
    """

    def __init__(
        self,
        agent: (
            SentimentAgent
            | None
        ) = None,
        sources: (
            list[
                BaseSentimentSource
            ]
            | None
        ) = None,
        config: (
            SentimentServiceConfig
            | None
        ) = None,
    ) -> None:

        self.agent = (
            agent
            if agent is not None
            else SentimentAgent()
        )

        self.config = (
            config
            if config is not None
            else SentimentServiceConfig()
        )

        self.sources = (
            list(
                sources
            )
            if sources is not None
            else [
                OKXSentimentSource()
            ]
        )

        self._closed = False

    async def __aenter__(
        self,
    ) -> "SentimentService":

        if self._closed:

            raise RuntimeError(
                "SentimentService "
                "is already closed."
            )

        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:

        await self.close()

    def add_source(
        self,
        source: BaseSentimentSource,
    ) -> None:
        """
        動態加入 sentiment source。
        """

        if self._closed:

            raise RuntimeError(
                "SentimentService "
                "is already closed."
            )

        self.sources.append(
            source
        )

    async def analyze(
        self,
        context: MarketContext,
    ) -> SentimentOutput:
        """
        執行完整 SENTIMENT pipeline。

        任何單一 source 失敗：

            不會讓整個 service
            直接失敗。

        只要其他 source 還有資料，
        SentimentAgent 就可以繼續分析。
        """

        if self._closed:

            raise RuntimeError(
                "SentimentService "
                "is already closed."
            )

        enabled_sources = [
            source
            for source
            in self.sources
            if source.enabled
        ]

        executions = (
            await asyncio.gather(
                *[
                    self._run_source(
                        source=source,
                        context=context,
                    )
                    for source
                    in enabled_sources
                ]
            )
        )

        source_results: list[
            SentimentSourceResult
        ] = []

        source_errors: list[
            str
        ] = []

        source_status: dict[
            str,
            dict[
                str,
                Any,
            ],
        ] = {}

        sources_succeeded = 0

        sources_with_data = 0

        for execution in executions:

            source_name = (
                execution.source.name
            )

            if (
                execution.error
                is not None
            ):

                error_message = (
                    f"{source_name}: "
                    f"{type(execution.error).__name__}: "
                    f"{execution.error}"
                )

                source_errors.append(
                    error_message
                )

                source_status[
                    source_name
                ] = {
                    "success":
                        False,

                    "has_data":
                        False,

                    "error":
                        error_message,
                }

                continue

            result = (
                execution.result
            )

            if result is None:

                error_message = (
                    f"{source_name}: "
                    "source returned no result."
                )

                source_errors.append(
                    error_message
                )

                source_status[
                    source_name
                ] = {
                    "success":
                        False,

                    "has_data":
                        False,

                    "error":
                        error_message,
                }

                continue

            sources_succeeded += 1

            has_data = (
                result.success
            )

            if has_data:

                sources_with_data += 1

            source_results.append(
                result
            )

            source_errors.extend(
                result.errors
            )

            source_status[
                source_name
            ] = {
                "success":
                    True,

                "has_data":
                    has_data,

                "errors":
                    list(
                        result.errors
                    ),

                "metadata":
                    dict(
                        result.metadata
                    ),
            }

        (
            payload,
            merge_metadata,
        ) = self._merge_source_results(
            context=context,
            results=source_results,
        )

        output = (
            await self.agent.analyze(
                context=context,
                payload=payload,
            )
        )

        return (
            self._attach_service_data(
                output=output,

                source_errors=(
                    source_errors
                ),

                source_status=(
                    source_status
                ),

                sources_requested=len(
                    enabled_sources
                ),

                sources_succeeded=(
                    sources_succeeded
                ),

                sources_with_data=(
                    sources_with_data
                ),

                merge_metadata=(
                    merge_metadata
                ),
            )
        )

    async def close(
        self,
    ) -> None:
        """
        關閉 sources。

        idempotent：
        可以重複呼叫。
        """

        if self._closed:

            return

        self._closed = True

        if not (
            self.config
            .close_sources_on_close
        ):

            return

        await asyncio.gather(
            *[
                source.close()
                for source
                in self.sources
                if not source.closed
            ],
            return_exceptions=True,
        )

    async def _run_source(
        self,
        source: BaseSentimentSource,
        context: MarketContext,
    ) -> _SourceExecutionResult:
        """
        單一 source isolation。

        包含：

        - timeout
        - exception isolation
        """

        try:

            result = (
                await asyncio.wait_for(
                    source.fetch(
                        context=context
                    ),
                    timeout=(
                        self.config
                        .source_timeout_seconds
                    ),
                )
            )

            return (
                _SourceExecutionResult(
                    source=source,
                    result=result,
                )
            )

        except Exception as exc:

            return (
                _SourceExecutionResult(
                    source=source,
                    error=exc,
                )
            )

    def _merge_source_results(
        self,
        context: MarketContext,
        results: list[
            SentimentSourceResult
        ],
    ) -> tuple[
        SentimentInput,
        dict[
            str,
            Any,
        ],
    ]:
        """
        將多個 source payload
        合併成單一 SentimentInput。

        Conflict policy：

        預設：

            preserve_first_value_on_conflict=True

        第一個 source 已提供某 key，
        後面的 source 不會直接覆蓋。

        同時把 conflict 記錄在 metadata，
        避免 silent overwrite。
        """

        social_data: dict[
            str,
            Any,
        ] = {}

        funding_rate_data: dict[
            str,
            Any,
        ] = {}

        open_interest_data: dict[
            str,
            Any,
        ] = {}

        long_short_ratio_data: dict[
            str,
            Any,
        ] = {}

        liquidation_data: dict[
            str,
            Any,
        ] = {}

        market_activity_data: dict[
            str,
            Any,
        ] = {}

        signals: list[
            SentimentSignal
        ] = []

        source_metadata: dict[
            str,
            Any,
        ] = {}

        conflicts: list[
            dict[
                str,
                Any,
            ]
        ] = []

        for result in results:

            payload = (
                result.payload
            )

            source_name = (
                result.source
            )

            source_metadata[
                source_name
            ] = {
                "result_metadata":
                    dict(
                        result.metadata
                    ),

                "payload_metadata":
                    dict(
                        payload.metadata
                    ),
            }

            self._merge_dict(
                target=social_data,
                incoming=(
                    payload.social_data
                ),
                category="social_data",
                source=source_name,
                conflicts=conflicts,
            )

            self._merge_dict(
                target=(
                    funding_rate_data
                ),
                incoming=(
                    payload
                    .funding_rate_data
                ),
                category=(
                    "funding_rate_data"
                ),
                source=source_name,
                conflicts=conflicts,
            )

            self._merge_dict(
                target=(
                    open_interest_data
                ),
                incoming=(
                    payload
                    .open_interest_data
                ),
                category=(
                    "open_interest_data"
                ),
                source=source_name,
                conflicts=conflicts,
            )

            self._merge_dict(
                target=(
                    long_short_ratio_data
                ),
                incoming=(
                    payload
                    .long_short_ratio_data
                ),
                category=(
                    "long_short_ratio_data"
                ),
                source=source_name,
                conflicts=conflicts,
            )

            self._merge_dict(
                target=(
                    liquidation_data
                ),
                incoming=(
                    payload
                    .liquidation_data
                ),
                category=(
                    "liquidation_data"
                ),
                source=source_name,
                conflicts=conflicts,
            )

            self._merge_dict(
                target=(
                    market_activity_data
                ),
                incoming=(
                    payload
                    .market_activity_data
                ),
                category=(
                    "market_activity_data"
                ),
                source=source_name,
                conflicts=conflicts,
            )

            signals.extend(
                payload.signals
            )

        if (
            self.config
            .include_context_market_data
            and context.market_data
        ):

            self._merge_dict(
                target=(
                    market_activity_data
                ),
                incoming=(
                    context.market_data
                ),
                category=(
                    "context_market_data"
                ),
                source=(
                    "market_context"
                ),
                conflicts=conflicts,
            )

        signals = (
            self._deduplicate_signals(
                signals
            )
        )

        metadata = {
            "service":
                "SentimentService",

            "sources": [
                result.source
                for result
                in results
            ],

            "source_metadata":
                source_metadata,

            "merge_conflicts":
                conflicts,

            "merge_conflict_count":
                len(
                    conflicts
                ),
        }

        payload = SentimentInput(
            social_data=(
                social_data
            ),

            funding_rate_data=(
                funding_rate_data
            ),

            open_interest_data=(
                open_interest_data
            ),

            long_short_ratio_data=(
                long_short_ratio_data
            ),

            liquidation_data=(
                liquidation_data
            ),

            market_activity_data=(
                market_activity_data
            ),

            signals=signals,

            metadata=metadata,
        )

        return (
            payload,
            metadata,
        )

    def _merge_dict(
        self,
        target: dict[
            str,
            Any,
        ],
        incoming: dict[
            str,
            Any,
        ],
        category: str,
        source: str,
        conflicts: list[
            dict[
                str,
                Any,
            ]
        ],
    ) -> None:
        """
        Merge dict with explicit
        conflict tracking。
        """

        if not incoming:

            return

        for (
            key,
            value,
        ) in incoming.items():

            if key not in target:

                target[
                    key
                ] = value

                continue

            existing = (
                target[
                    key
                ]
            )

            if existing == value:

                continue

            conflicts.append(
                {
                    "category":
                        category,

                    "key":
                        key,

                    "existing":
                        existing,

                    "incoming":
                        value,

                    "incoming_source":
                        source,
                }
            )

            if not (
                self.config
                .preserve_first_value_on_conflict
            ):

                target[
                    key
                ] = value

    @staticmethod
    def _deduplicate_signals(
        signals: list[
            SentimentSignal
        ],
    ) -> list[
        SentimentSignal
    ]:
        """
        避免不同 orchestration path
        將完全相同 signal 重複加入。

        identity：

            source
            name
            timestamp
            score
            value
        """

        result: list[
            SentimentSignal
        ] = []

        seen: set[
            str
        ] = set()

        for signal in signals:

            try:

                value_key = (
                    signal.model_dump_json(
                        exclude={
                            "metadata",
                        }
                    )
                )

            except Exception:

                value_key = (
                    f"{signal.source.value}|"
                    f"{signal.name}|"
                    f"{signal.timestamp.isoformat()}|"
                    f"{signal.score}|"
                    f"{signal.value!r}"
                )

            if value_key in seen:

                continue

            seen.add(
                value_key
            )

            result.append(
                signal
            )

        return result

    @staticmethod
    def _attach_service_data(
        output: SentimentOutput,
        source_errors: list[
            str
        ],
        source_status: dict[
            str,
            dict[
                str,
                Any,
            ],
        ],
        sources_requested: int,
        sources_succeeded: int,
        sources_with_data: int,
        merge_metadata: dict[
            str,
            Any,
        ],
    ) -> SentimentOutput:
        """
        將 ingestion / service metadata
        加到 SentimentOutput。

        partial source failure：

            不強制改成 ERROR。

        Agent 自己的 SUCCESS / SKIPPED /
        ERROR status 保留。
        """

        data = dict(
            output.data
        )

        data.update(
            {
                "sources_requested":
                    sources_requested,

                "sources_succeeded":
                    sources_succeeded,

                "sources_with_data":
                    sources_with_data,

                "source_status":
                    source_status,

                "source_errors":
                    list(
                        source_errors
                    ),

                "merge_conflicts":
                    merge_metadata.get(
                        "merge_conflicts",
                        [],
                    ),

                "merge_conflict_count":
                    merge_metadata.get(
                        "merge_conflict_count",
                        0,
                    ),

                "sentiment_service":
                    True,
            }
        )

        errors = list(
            output.errors
        )

        for error in source_errors:

            if error not in errors:

                errors.append(
                    error
                )

        return output.model_copy(
            update={
                "data":
                    data,

                "errors":
                    errors,
            },
            deep=True,
        )
