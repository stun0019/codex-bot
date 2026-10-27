from __future__ import annotations

import asyncio

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
)

from ....exchanges.okx.client import (
    OKXPublicClient,
)

from ....exchanges.okx.constants import (
    Bar,
    OKX_REST_BASE_URL,
)

from ....exchanges.okx.models import (
    Candle,
)

from ...models import (
    MarketContext,
)

from ..models import (
    CandleData,
    ChartsInput,
)

from .base import (
    BaseChartsSource,
    ChartsSourceConfig,
    ChartsSourceResult,
)


@dataclass(slots=True)
class OKXChartsSourceConfig(
    ChartsSourceConfig
):
    """
    OKX CHARTS Source 設定。

    使用：

        OKX public candle API

    不需要：

        API Key
        Secret
        Passphrase
    """

    name: str = (
        "okx_charts"
    )

    base_url: str = (
        OKX_REST_BASE_URL
    )

    default_timeframes: list[
        str
    ] = field(
        default_factory=lambda: [
            "15m",
            "1H",
            "4H",
        ]
    )

    candle_limit: int = 300

    use_context_timeframes: bool = True

    include_unconfirmed: bool = True

    max_retries: int = 3

    def __post_init__(
        self,
    ) -> None:

        super(
            OKXChartsSourceConfig,
            self,
        ).__post_init__()

        self.base_url = (
            self.base_url
            .strip()
            .rstrip("/")
        )

        if not self.base_url:

            raise ValueError(
                "OKX base_url cannot "
                "be empty."
            )

        if not (
            1
            <=
            self.candle_limit
            <=
            300
        ):

            raise ValueError(
                "candle_limit must be "
                "between 1 and 300."
            )

        if self.max_retries < 1:

            raise ValueError(
                "max_retries must "
                "be at least 1."
            )

        if not (
            self.default_timeframes
        ):

            raise ValueError(
                "default_timeframes "
                "cannot be empty."
            )

        self.default_timeframes = (
            self.normalize_timeframes(
                self.default_timeframes
            )
        )


@dataclass(slots=True)
class _TimeframeFetchResult:
    """
    OKX source 內部使用。
    """

    timeframe: str

    candles: list[
        CandleData
    ] = field(
        default_factory=list
    )

    error: (
        Exception
        | None
    ) = None


class OKXChartsSource(
    BaseChartsSource
):
    """
    OKX multi-timeframe
    OHLCV source。

    Pipeline：

        MarketContext
            ↓
        Resolve timeframes
            ↓
        OKX get_candles()
            ↓
        Concurrent requests
            ↓
        CandleData normalization
            ↓
        ChartsInput

    支援 partial failure：

        例如：

        15m SUCCESS
        1H  SUCCESS
        4H  ERROR

    CHARTS pipeline 仍可繼續分析
    15m + 1H。
    """

    def __init__(
        self,
        config: (
            OKXChartsSourceConfig
            | None
        ) = None,
        client: (
            OKXPublicClient
            | None
        ) = None,
    ) -> None:

        resolved_config = (
            config
            if config is not None
            else (
                OKXChartsSourceConfig()
            )
        )

        super().__init__(
            resolved_config
        )

        self.config: (
            OKXChartsSourceConfig
        ) = resolved_config

        self._owns_client = (
            client is None
        )

        self._client = (
            client
            if client is not None
            else OKXPublicClient(
                base_url=(
                    self.config
                    .base_url
                ),

                timeout=(
                    self.config
                    .timeout_seconds
                ),

                max_retries=(
                    self.config
                    .max_retries
                ),
            )
        )

        self.last_errors: list[
            str
        ] = []

    async def fetch(
        self,
        context: MarketContext,
    ) -> ChartsSourceResult:
        """
        抓取 MarketContext 指定 symbol
        的 multi-timeframe candles。
        """

        self.ensure_available()

        self.last_errors = []

        symbol = (
            self.normalize_symbol(
                context.symbol
            )
        )

        timeframes = (
            self._resolve_timeframes(
                context
            )
        )

        if not timeframes:

            return ChartsSourceResult(
                source=self.name,

                payload=(
                    ChartsInput(
                        metadata={
                            "source":
                                self.name,

                            "exchange":
                                "OKX",

                            "symbol":
                                symbol,

                            "reason":
                                "no_timeframes",
                        }
                    )
                ),

                errors=[
                    "No timeframes were "
                    "configured."
                ],

                metadata={
                    "exchange":
                        "OKX",

                    "symbol":
                        symbol,

                    "timeframes_requested":
                        [],
                },
            )

        executions = (
            await asyncio.gather(
                *[
                    self._fetch_timeframe(
                        symbol=symbol,
                        timeframe=timeframe,
                    )
                    for timeframe
                    in timeframes
                ]
            )
        )

        candles_by_timeframe: dict[
            str,
            list[
                CandleData
            ],
        ] = {}

        timeframe_status: dict[
            str,
            dict[
                str,
                Any,
            ],
        ] = {}

        for execution in executions:

            timeframe = (
                execution.timeframe
            )

            if (
                execution.error
                is not None
            ):

                message = (
                    f"{timeframe}: "
                    f"{type(execution.error).__name__}: "
                    f"{execution.error}"
                )

                self.last_errors.append(
                    message
                )

                timeframe_status[
                    timeframe
                ] = {
                    "success":
                        False,

                    "candle_count":
                        0,

                    "error":
                        message,
                }

                continue

            candles = (
                execution.candles
            )

            if candles:

                candles_by_timeframe[
                    timeframe
                ] = candles

            timeframe_status[
                timeframe
            ] = {
                "success":
                    True,

                "candle_count":
                    len(
                        candles
                    ),

                "confirmed_count":
                    sum(
                        1
                        for candle
                        in candles
                        if candle.confirmed
                    ),

                "unconfirmed_count":
                    sum(
                        1
                        for candle
                        in candles
                        if not candle.confirmed
                    ),
            }

        payload = ChartsInput(
            candles=(
                candles_by_timeframe
            ),

            indicators={},

            structure_data={},

            metadata={
                "source":
                    self.name,

                "exchange":
                    "OKX",

                "symbol":
                    symbol,

                "timeframes_requested":
                    timeframes,

                "timeframes_received":
                    list(
                        candles_by_timeframe
                        .keys()
                    ),

                "timeframe_status":
                    timeframe_status,

                "source_errors":
                    list(
                        self.last_errors
                    ),

                "candle_limit":
                    self.config
                    .candle_limit,
            },
        )

        return ChartsSourceResult(
            source=self.name,

            payload=payload,

            errors=list(
                self.last_errors
            ),

            metadata={
                "exchange":
                    "OKX",

                "symbol":
                    symbol,

                "timeframes_requested":
                    timeframes,

                "timeframes_succeeded":
                    sum(
                        1
                        for value
                        in (
                            timeframe_status
                            .values()
                        )
                        if value.get(
                            "success"
                        )
                    ),

                "timeframes_with_data":
                    len(
                        candles_by_timeframe
                    ),

                "timeframe_status":
                    timeframe_status,

                "candle_limit":
                    self.config
                    .candle_limit,
            },
        )

    async def close(
        self,
    ) -> None:

        if self.closed:

            return

        if self._owns_client:

            try:

                await (
                    self._client
                    .close()
                )

            finally:

                await super().close()

            return

        await super().close()

    # =================================
    # Timeframes
    # =================================

    def _resolve_timeframes(
        self,
        context: MarketContext,
    ) -> list[
        str
    ]:
        """
        優先：

            MarketContext.timeframes

        fallback：

            config.default_timeframes
        """

        if (
            self.config
            .use_context_timeframes
            and context.timeframes
        ):

            source_timeframes = (
                context.timeframes
            )

        else:

            source_timeframes = (
                self.config
                .default_timeframes
            )

        return (
            self.normalize_timeframes(
                list(
                    source_timeframes
                )
            )
        )

    # =================================
    # Fetch one timeframe
    # =================================

    async def _fetch_timeframe(
        self,
        symbol: str,
        timeframe: str,
    ) -> _TimeframeFetchResult:

        try:

            bar = (
                self._resolve_bar(
                    timeframe
                )
            )

            raw_candles = (
                await self._client
                .get_candles(
                    inst_id=symbol,

                    bar=bar,

                    limit=(
                        self.config
                        .candle_limit
                    ),
                )
            )

            candles = (
                self._normalize_candles(
                    raw_candles
                )
            )

            if not (
                self.config
                .include_unconfirmed
            ):

                candles = [
                    candle
                    for candle
                    in candles
                    if candle.confirmed
                ]

            return (
                _TimeframeFetchResult(
                    timeframe=(
                        timeframe
                    ),

                    candles=(
                        candles
                    ),
                )
            )

        except Exception as exc:

            return (
                _TimeframeFetchResult(
                    timeframe=(
                        timeframe
                    ),

                    error=exc,
                )
            )

    # =================================
    # OKX Bar mapping
    # =================================

    @staticmethod
    def _resolve_bar(
        timeframe: str,
    ) -> Bar:
        """
        CHARTS timeframe
            ↓
        OKX Bar enum

        注意：

        OKX 的部分長週期使用
        UTC bar enum。
        """

        mapping: dict[
            str,
            Bar,
        ] = {
            "1m":
                Bar.M1,

            "3m":
                Bar.M3,

            "5m":
                Bar.M5,

            "15m":
                Bar.M15,

            "30m":
                Bar.M30,

            "1H":
                Bar.H1,

            "2H":
                Bar.H2,

            "4H":
                Bar.H4,

            "6H":
                Bar.H6_UTC,

            "12H":
                Bar.H12_UTC,

            "1D":
                Bar.D1_UTC,

            "2D":
                Bar.D2_UTC,

            "3D":
                Bar.D3_UTC,

            "1W":
                Bar.W1_UTC,

            "1M":
                Bar.MN1_UTC,

            "3M":
                Bar.MN3_UTC,
        }

        bar = (
            mapping.get(
                timeframe
            )
        )

        if bar is None:

            supported = (
                ", ".join(
                    mapping.keys()
                )
            )

            raise ValueError(
                (
                    "Unsupported OKX "
                    f"timeframe: "
                    f"{timeframe!r}. "
                    f"Supported: "
                    f"{supported}"
                )
            )

        return bar

    # =================================
    # Candle normalization
    # =================================

    @classmethod
    def _normalize_candles(
        cls,
        candles: list[
            Candle
        ],
    ) -> list[
        CandleData
    ]:
        """
        OKX Candle
            ↓
        CHARTS CandleData

        同時：

            - chronological sort
            - timestamp dedupe
        """

        normalized: dict[
            datetime,
            CandleData,
        ] = {}

        for candle in candles:

            item = (
                cls._convert_candle(
                    candle
                )
            )

            normalized[
                item.timestamp
            ] = item

        return sorted(
            normalized.values(),
            key=lambda candle:
                candle.timestamp,
        )

    @staticmethod
    def _convert_candle(
        candle: Candle,
    ) -> CandleData:

        return CandleData(
            timestamp=(
                candle.timestamp
            ),

            open=float(
                candle.open
            ),

            high=float(
                candle.high
            ),

            low=float(
                candle.low
            ),

            close=float(
                candle.close
            ),

            volume=float(
                candle.volume
            ),

            volume_currency=(
                float(
                    candle
                    .volume_currency
                )
                if (
                    candle
                    .volume_currency
                    is not None
                )
                else None
            ),

            volume_quote=(
                float(
                    candle
                    .volume_quote
                )
                if (
                    candle
                    .volume_quote
                    is not None
                )
                else None
            ),

            confirmed=(
                candle.confirmed
            ),

            metadata={
                "exchange":
                    "OKX",
            },
        )
