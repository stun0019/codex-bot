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
    ChartsAgent,
)

from .models import (
    CandleData,
    ChartsInput,
    ChartsOutput,
)

from .sources import (
    BaseChartsSource,
    ChartsSourceResult,
    OKXChartsSource,
)


@dataclass(slots=True)
class ChartsServiceConfig:
    """
    CHARTS orchestration 設定。

    ChartsService 負責：

        Sources
            ↓
        ChartsInput
            ↓
        ChartsAgent
            ↓
        ChartsOutput

    Service 不負責：

        - indicator calculation
        - technical scoring
        - market structure analysis
        - trade decision
        - execution
    """

    source_timeout_seconds: float = 30.0

    preserve_first_timeframe_on_conflict: bool = True

    merge_context_market_data: bool = True

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
    Service 內部使用。
    """

    source: BaseChartsSource

    result: (
        ChartsSourceResult
        | None
    ) = None

    error: (
        Exception
        | None
    ) = None


class ChartsService:
    """
    CHARTS 完整 orchestration service。

    Pipeline：

        OKX / Future Sources
                ↓
        concurrent fetch
                ↓
        partial failure isolation
                ↓
        ChartsInput merge
                ↓
        ChartsAgent
                ↓
        ChartsOutput

    預設：

        OKXChartsSource

    未來可以加入：

        DatabaseChartsSource
        BacktestChartsSource
        BinanceChartsSource
        BingXChartsSource

    不需要修改 ChartsAgent。
    """

    def __init__(
        self,
        agent: (
            ChartsAgent
            | None
        ) = None,
        sources: (
            list[
                BaseChartsSource
            ]
            | None
        ) = None,
        config: (
            ChartsServiceConfig
            | None
        ) = None,
    ) -> None:

        self.agent = (
            agent
            if agent is not None
            else ChartsAgent()
        )

        self.config = (
            config
            if config is not None
            else ChartsServiceConfig()
        )

        self.sources = (
            list(
                sources
            )
            if sources is not None
            else [
                OKXChartsSource()
            ]
        )

        self._closed = False

    async def __aenter__(
        self,
    ) -> "ChartsService":

        if self._closed:

            raise RuntimeError(
                "ChartsService "
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

    # =================================
    # Source management
    # =================================

    def add_source(
        self,
        source: BaseChartsSource,
    ) -> None:
        """
        動態加入 CHARTS source。
        """

        if self._closed:

            raise RuntimeError(
                "ChartsService "
                "is already closed."
            )

        self.sources.append(
            source
        )

    # =================================
    # Main pipeline
    # =================================

    async def analyze(
        self,
        context: MarketContext,
    ) -> ChartsOutput:
        """
        執行完整 CHARTS pipeline。

        單一 source 失敗：

            不會直接讓整個 service
            失敗。

        只要還有任何 source
        提供 candle data，
        ChartsAgent 就會繼續分析。
        """

        if self._closed:

            raise RuntimeError(
                "ChartsService "
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
            ChartsSourceResult
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

                message = (
                    f"{source_name}: "
                    f"{type(execution.error).__name__}: "
                    f"{execution.error}"
                )

                source_errors.append(
                    message
                )

                source_status[
                    source_name
                ] = {
                    "success":
                        False,

                    "has_data":
                        False,

                    "error":
                        message,
                }

                continue

            result = (
                execution.result
            )

            if result is None:

                message = (
                    f"{source_name}: "
                    "source returned no result."
                )

                source_errors.append(
                    message
                )

                source_status[
                    source_name
                ] = {
                    "success":
                        False,

                    "has_data":
                        False,

                    "error":
                        message,
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

    # =================================
    # Close
    # =================================

    async def close(
        self,
    ) -> None:
        """
        關閉 sources。

        idempotent。
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

    # =================================
    # Source execution
    # =================================

    async def _run_source(
        self,
        source: BaseChartsSource,
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

    # =================================
    # Merge
    # =================================

    def _merge_source_results(
        self,
        context: MarketContext,
        results: list[
            ChartsSourceResult
        ],
    ) -> tuple[
        ChartsInput,
        dict[
            str,
            Any,
        ],
    ]:
        """
        將多個 source 合併成
        單一 ChartsInput。

        主要 merge 對象：

            candles[timeframe]

        預設：

            第一個 source 的 timeframe
            candle data 優先保留。

        避免不同 source
        silent overwrite。
        """

        candles: dict[
            str,
            list[
                CandleData
            ],
        ] = {}

        indicators: dict[
            str,
            Any,
        ] = {}

        structure_data: dict[
            str,
            Any,
        ] = {}

        conflicts: list[
            dict[
                str,
                Any,
            ]
        ] = []

        source_metadata: dict[
            str,
            Any,
        ] = {}

        timeframe_sources: dict[
            str,
            str,
        ] = {}

        for result in results:

            source_name = (
                result.source
            )

            payload = (
                result.payload
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

            for (
                timeframe,
                source_candles,
            ) in (
                payload
                .candles
                .items()
            ):

                if not source_candles:

                    continue

                if (
                    timeframe
                    not in candles
                ):

                    candles[
                        timeframe
                    ] = (
                        self._normalize_candles(
                            source_candles
                        )
                    )

                    timeframe_sources[
                        timeframe
                    ] = (
                        source_name
                    )

                    continue

                existing = (
                    candles[
                        timeframe
                    ]
                )

                incoming = (
                    self._normalize_candles(
                        source_candles
                    )
                )

                conflict = {
                    "category":
                        "candles",

                    "timeframe":
                        timeframe,

                    "existing_source":
                        timeframe_sources
                        .get(
                            timeframe
                        ),

                    "incoming_source":
                        source_name,

                    "existing_count":
                        len(
                            existing
                        ),

                    "incoming_count":
                        len(
                            incoming
                        ),
                }

                conflicts.append(
                    conflict
                )

                if not (
                    self.config
                    .preserve_first_timeframe_on_conflict
                ):

                    candles[
                        timeframe
                    ] = incoming

                    timeframe_sources[
                        timeframe
                    ] = (
                        source_name
                    )

            self._merge_dict(
                target=indicators,

                incoming=(
                    payload.indicators
                ),

                category="indicators",

                source=source_name,

                conflicts=conflicts,
            )

            self._merge_dict(
                target=structure_data,

                incoming=(
                    payload
                    .structure_data
                ),

                category=(
                    "structure_data"
                ),

                source=source_name,

                conflicts=conflicts,
            )

        if (
            self.config
            .merge_context_market_data
            and context.market_data
        ):

            self._merge_dict(
                target=structure_data,

                incoming={
                    "market_context":
                        dict(
                            context
                            .market_data
                        )
                },

                category=(
                    "context_market_data"
                ),

                source=(
                    "market_context"
                ),

                conflicts=conflicts,
            )

        metadata = {
            "service":
                "ChartsService",

            "sources": [
                result.source
                for result
                in results
            ],

            "source_metadata":
                source_metadata,

            "timeframe_sources":
                timeframe_sources,

            "timeframes_merged":
                list(
                    candles.keys()
                ),

            "merge_conflicts":
                conflicts,

            "merge_conflict_count":
                len(
                    conflicts
                ),
        }

        payload = ChartsInput(
            candles=candles,

            indicators=indicators,

            structure_data=(
                structure_data
            ),

            metadata=metadata,
        )

        return (
            payload,
            metadata,
        )

    # =================================
    # Dict merge
    # =================================

    @staticmethod
    def _merge_dict(
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
        通用 dict merge。

        預設保留第一個 value，
        conflict 被記錄。
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

    # =================================
    # Candle normalization
    # =================================

    @staticmethod
    def _normalize_candles(
        candles: list[
            CandleData
        ],
    ) -> list[
        CandleData
    ]:
        """
        保證：

            oldest
                ↓
            newest

        並依 timestamp 去重。
        """

        deduplicated: dict[
            Any,
            CandleData,
        ] = {}

        for candle in candles:

            deduplicated[
                candle.timestamp
            ] = candle

        return sorted(
            deduplicated.values(),
            key=lambda candle:
                candle.timestamp,
        )

    # =================================
    # Service output metadata
    # =================================

    @staticmethod
    def _attach_service_data(
        output: ChartsOutput,
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
    ) -> ChartsOutput:
        """
        將 source / service 狀態
        附加到 ChartsOutput。

        partial failure：

            不強制把 Agent status
            改成 ERROR。
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

                "timeframe_sources":
                    merge_metadata.get(
                        "timeframe_sources",
                        {},
                    ),

                "timeframes_merged":
                    merge_metadata.get(
                        "timeframes_merged",
                        [],
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

                "charts_service":
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
