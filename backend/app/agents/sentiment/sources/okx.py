from __future__ import annotations

import asyncio

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Awaitable,
    Callable,
)

import httpx

from ....exchanges.okx.client import (
    OKXPublicClient,
)

from ....exchanges.okx.constants import (
    InstrumentType,
    OKX_REST_BASE_URL,
)

from ...models import (
    MarketContext,
)

from ..models import (
    SentimentInput,
)

from .base import (
    BaseSentimentSource,
    SentimentSourceConfig,
    SentimentSourceResult,
)


@dataclass(slots=True)
class OKXSentimentSourceConfig(
    SentimentSourceConfig
):
    """
    OKX SENTIMENT Source 設定。

    所有使用的 endpoint
    都是 public endpoint。

    不需要：

        API Key
        Secret
        Passphrase
    """

    name: str = (
        "okx_sentiment"
    )

    base_url: str = (
        OKX_REST_BASE_URL
    )

    period: str = "1H"

    include_funding: bool = True

    include_open_interest: bool = True

    include_long_short_ratio: bool = True

    include_market_activity: bool = True

    include_liquidations: bool = True

    liquidation_limit: int = 100

    max_retries: int = 3

    retry_delay_seconds: float = 0.4

    user_agent: str = (
        "codex-bot/1.0"
    )

    def __post_init__(
        self,
    ) -> None:

        super(
            OKXSentimentSourceConfig,
            self,
        ).__post_init__()

        self.base_url = (
            self.base_url
            .strip()
            .rstrip("/")
        )

        if not self.base_url:

            raise ValueError(
                "OKX base_url "
                "cannot be empty."
            )

        if (
            self.period
            not in (
                "5m",
                "1H",
                "1D",
            )
        ):

            raise ValueError(
                (
                    "OKX Rubik period "
                    "must be one of: "
                    "5m, 1H, 1D."
                )
            )

        if not (
            1
            <=
            self.liquidation_limit
            <=
            100
        ):

            raise ValueError(
                (
                    "liquidation_limit "
                    "must be between "
                    "1 and 100."
                )
            )

        if self.max_retries < 1:

            raise ValueError(
                "max_retries must "
                "be at least 1."
            )

        if (
            self.retry_delay_seconds
            <
            0
        ):

            raise ValueError(
                (
                    "retry_delay_seconds "
                    "cannot be negative."
                )
            )


class OKXSentimentSource(
    BaseSentimentSource
):
    """
    OKX 公開市場 sentiment /
    positioning source。

    Pipeline:

        OKX Public APIs
            ↓
        Funding
        Open Interest
        OI History
        Long/Short Ratio
        Liquidations
        Ticker Activity
            ↓
        SentimentInput

    注意：

    這層只負責資料收集與
    normalization。

    不在這裡做：

        - LONG / SHORT 決策
        - composite sentiment
        - crowding regime
        - trade execution
    """

    LONG_SHORT_ENDPOINT = (
        "/api/v5/rubik/stat/"
        "contracts/"
        "long-short-account-ratio"
    )

    OPEN_INTEREST_VOLUME_ENDPOINT = (
        "/api/v5/rubik/stat/"
        "contracts/"
        "open-interest-volume"
    )

    LIQUIDATION_ENDPOINT = (
        "/api/v5/public/"
        "liquidation-orders"
    )

    def __init__(
        self,
        config: (
            OKXSentimentSourceConfig
            | None
        ) = None,
        okx_client: (
            OKXPublicClient
            | None
        ) = None,
        http_client: (
            httpx.AsyncClient
            | None
        ) = None,
    ) -> None:

        resolved_config = (
            config
            if config is not None
            else (
                OKXSentimentSourceConfig()
            )
        )

        super().__init__(
            resolved_config
        )

        self.config: (
            OKXSentimentSourceConfig
        ) = resolved_config

        self._owns_okx_client = (
            okx_client is None
        )

        self._owns_http_client = (
            http_client is None
        )

        self._okx = (
            okx_client
            if okx_client is not None
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

        self._http = (
            http_client
            if http_client is not None
            else httpx.AsyncClient(
                base_url=(
                    self.config
                    .base_url
                ),
                timeout=(
                    self.config
                    .timeout_seconds
                ),
                headers={
                    "Accept":
                        "application/json",

                    "User-Agent":
                        self.config
                        .user_agent,
                },
            )
        )

        self.last_errors: list[
            str
        ] = []

    async def fetch(
        self,
        context: MarketContext,
    ) -> SentimentSourceResult:
        """
        從 OKX 收集所有可用的
        sentiment / positioning data。

        任一 endpoint 失敗時：

            不會讓其他 endpoint
            一起失敗。

        屬於 partial failure design。
        """

        self.ensure_available()

        self.last_errors = []

        symbol = (
            self.normalize_symbol(
                context.symbol
            )
        )

        base_asset = (
            self.extract_base_asset(
                symbol
            )
        )

        instrument_family = (
            self
            .extract_instrument_family(
                symbol
            )
        )

        tasks: list[
            tuple[
                str,
                Awaitable[
                    dict[
                        str,
                        Any,
                    ]
                ],
            ]
        ] = []

        if (
            self.config
            .include_funding
            and symbol.endswith(
                "-SWAP"
            )
        ):

            tasks.append(
                (
                    "funding",
                    self._fetch_funding(
                        symbol
                    ),
                )
            )

        if (
            self.config
            .include_open_interest
        ):

            tasks.append(
                (
                    "open_interest_current",
                    self
                    ._fetch_current_open_interest(
                        symbol
                    ),
                )
            )

            tasks.append(
                (
                    "open_interest_history",
                    self
                    ._fetch_open_interest_history(
                        base_asset
                    ),
                )
            )

        if (
            self.config
            .include_long_short_ratio
        ):

            tasks.append(
                (
                    "long_short_ratio",
                    self
                    ._fetch_long_short_ratio(
                        base_asset
                    ),
                )
            )

        if (
            self.config
            .include_market_activity
        ):

            tasks.append(
                (
                    "market_activity",
                    self
                    ._fetch_market_activity(
                        symbol
                    ),
                )
            )

        if (
            self.config
            .include_liquidations
            and symbol.endswith(
                "-SWAP"
            )
        ):

            tasks.append(
                (
                    "liquidations",
                    self
                    ._fetch_liquidations(
                        instrument_family
                    ),
                )
            )

        results = await asyncio.gather(
            *[
                self._run_component(
                    name=name,
                    operation=operation,
                )
                for (
                    name,
                    operation,
                )
                in tasks
            ]
        )

        funding_data: dict[
            str,
            Any,
        ] = {}

        open_interest_data: dict[
            str,
            Any,
        ] = {}

        long_short_data: dict[
            str,
            Any,
        ] = {}

        market_activity_data: dict[
            str,
            Any,
        ] = {}

        liquidation_data: dict[
            str,
            Any,
        ] = {}

        component_status: dict[
            str,
            bool,
        ] = {}

        for (
            component_name,
            data,
            error,
        ) in results:

            component_status[
                component_name
            ] = (
                error is None
            )

            if error is not None:

                message = (
                    f"{component_name}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                self.last_errors.append(
                    message
                )

                continue

            if not data:

                continue

            if (
                component_name
                ==
                "funding"
            ):

                funding_data.update(
                    data
                )

            elif (
                component_name
                in (
                    "open_interest_current",
                    "open_interest_history",
                )
            ):

                open_interest_data.update(
                    data
                )

            elif (
                component_name
                ==
                "long_short_ratio"
            ):

                long_short_data.update(
                    data
                )

            elif (
                component_name
                ==
                "market_activity"
            ):

                market_activity_data.update(
                    data
                )

            elif (
                component_name
                ==
                "liquidations"
            ):

                liquidation_data.update(
                    data
                )

        payload = SentimentInput(
            funding_rate_data=(
                funding_data
            ),

            open_interest_data=(
                open_interest_data
            ),

            long_short_ratio_data=(
                long_short_data
            ),

            liquidation_data=(
                liquidation_data
            ),

            market_activity_data=(
                market_activity_data
            ),

            metadata={
                "source":
                    self.name,

                "exchange":
                    "OKX",

                "symbol":
                    symbol,

                "base_asset":
                    base_asset,

                "instrument_family":
                    instrument_family,

                "period":
                    self.config
                    .period,

                "component_status":
                    component_status,

                "source_errors":
                    list(
                        self.last_errors
                    ),
            },
        )

        return SentimentSourceResult(
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

                "base_asset":
                    base_asset,

                "instrument_family":
                    instrument_family,

                "period":
                    self.config
                    .period,

                "components_requested":
                    len(
                        tasks
                    ),

                "components_succeeded":
                    sum(
                        1
                        for success
                        in (
                            component_status
                            .values()
                        )
                        if success
                    ),

                "component_status":
                    component_status,
            },
        )

    async def close(
        self,
    ) -> None:

        if self.closed:

            return

        errors: list[
            Exception
        ] = []

        if self._owns_okx_client:

            try:

                await self._okx.close()

            except Exception as exc:

                errors.append(
                    exc
                )

        if self._owns_http_client:

            try:

                await self._http.aclose()

            except Exception as exc:

                errors.append(
                    exc
                )

        await super().close()

        _ = errors

    async def _run_component(
        self,
        name: str,
        operation: Awaitable[
            dict[
                str,
                Any,
            ]
        ],
    ) -> tuple[
        str,
        dict[
            str,
            Any,
        ],
        Exception | None,
    ]:

        try:

            result = await operation

            return (
                name,
                result,
                None,
            )

        except Exception as exc:

            return (
                name,
                {},
                exc,
            )

    # =================================
    # Funding
    # =================================

    async def _fetch_funding(
        self,
        symbol: str,
    ) -> dict[
        str,
        Any,
    ]:

        funding = (
            await self._okx
            .get_funding_rate(
                symbol
            )
        )

        rate = (
            self.safe_float(
                funding
                .funding_rate
            )
        )

        data: dict[
            str,
            Any,
        ] = {
            "source":
                "OKX",

            "symbol":
                symbol,
        }

        if rate is not None:

            data[
                "funding_rate"
            ] = rate

        if (
            funding.funding_time
            is not None
        ):

            data[
                "funding_time"
            ] = (
                funding
                .funding_time
                .isoformat()
            )

        if (
            funding
            .next_funding_time
            is not None
        ):

            data[
                "next_funding_time"
            ] = (
                funding
                .next_funding_time
                .isoformat()
            )

        min_rate = (
            self.safe_float(
                funding
                .min_funding_rate
            )
        )

        max_rate = (
            self.safe_float(
                funding
                .max_funding_rate
            )
        )

        if min_rate is not None:

            data[
                "min_funding_rate"
            ] = min_rate

        if max_rate is not None:

            data[
                "max_funding_rate"
            ] = max_rate

        return data

    # =================================
    # Current Open Interest
    # =================================

    async def _fetch_current_open_interest(
        self,
        symbol: str,
    ) -> dict[
        str,
        Any,
    ]:

        values = (
            await self._okx
            .get_open_interest(
                inst_type=(
                    InstrumentType.SWAP
                ),
                inst_id=symbol,
            )
        )

        if not values:

            return {}

        item = next(
            (
                value
                for value
                in values
                if (
                    value.inst_id
                    ==
                    symbol
                )
            ),
            values[0],
        )

        return {
            "spot_current_oi":
                self.safe_float(
                    item.open_interest
                ),

            "spot_current_oi_ccy":
                self.safe_float(
                    item
                    .open_interest_ccy
                ),

            "spot_current_oi_usd":
                self.safe_float(
                    item
                    .open_interest_usd
                ),

            "spot_current_timestamp":
                (
                    item.timestamp
                    .isoformat()
                ),

            "source":
                "OKX",
        }

    # =================================
    # Historical OI
    # =================================

    async def _fetch_open_interest_history(
        self,
        base_asset: str,
    ) -> dict[
        str,
        Any,
    ]:

        rows = await self._raw_get(
            self
            .OPEN_INTEREST_VOLUME_ENDPOINT,

            {
                "ccy":
                    base_asset,

                "period":
                    self.config
                    .period,
            },
        )

        points: list[
            tuple[
                int,
                float,
                float | None,
            ]
        ] = []

        for row in rows:

            parsed = (
                self._parse_oi_point(
                    row
                )
            )

            if parsed is not None:

                points.append(
                    parsed
                )

        if not points:

            return {}

        points.sort(
            key=lambda item:
                item[0]
        )

        latest = (
            points[-1]
        )

        previous = (
            points[-2]
            if len(points) >= 2
            else None
        )

        timestamp_ms = (
            latest[0]
        )

        current_oi = (
            latest[1]
        )

        current_volume = (
            latest[2]
        )

        data: dict[
            str,
            Any,
        ] = {
            "current":
                current_oi,

            "timestamp":
                self._ms_to_iso(
                    timestamp_ms
                ),

            "history_count":
                len(
                    points
                ),

            "period":
                self.config
                .period,

            "currency":
                base_asset,

            "source":
                "OKX_RUBIK",
        }

        if (
            current_volume
            is not None
        ):

            data[
                "volume"
            ] = current_volume

        if previous is not None:

            previous_oi = (
                previous[1]
            )

            data[
                "previous"
            ] = previous_oi

            data[
                "previous_timestamp"
            ] = (
                self._ms_to_iso(
                    previous[0]
                )
            )

            if previous_oi != 0:

                data[
                    "change_pct"
                ] = (
                    (
                        current_oi
                        -
                        previous_oi
                    )
                    /
                    previous_oi
                    *
                    100
                )

        return data

    # =================================
    # Long / Short
    # =================================

    async def _fetch_long_short_ratio(
        self,
        base_asset: str,
    ) -> dict[
        str,
        Any,
    ]:

        rows = await self._raw_get(
            self
            .LONG_SHORT_ENDPOINT,

            {
                "ccy":
                    base_asset,

                "period":
                    self.config
                    .period,
            },
        )

        points: list[
            tuple[
                int,
                float,
            ]
        ] = []

        for row in rows:

            parsed = (
                self
                ._parse_long_short_point(
                    row
                )
            )

            if parsed is not None:

                points.append(
                    parsed
                )

        if not points:

            return {}

        points.sort(
            key=lambda item:
                item[0]
        )

        latest = (
            points[-1]
        )

        ratio = (
            latest[1]
        )

        result: dict[
            str,
            Any,
        ] = {
            "ratio":
                ratio,

            "timestamp":
                self._ms_to_iso(
                    latest[0]
                ),

            "period":
                self.config
                .period,

            "currency":
                base_asset,

            # 此 endpoint 是
            # currency-level futures /
            # perpetual positioning，
            # 不是單一 contract ratio。
            "scope":
                "currency",

            "source":
                "OKX_RUBIK",
        }

        if len(points) >= 2:

            previous_ratio = (
                points[-2][1]
            )

            result[
                "previous_ratio"
            ] = (
                previous_ratio
            )

            result[
                "ratio_change"
            ] = (
                ratio
                -
                previous_ratio
            )

        return result

    # =================================
    # Market Activity
    # =================================

    async def _fetch_market_activity(
        self,
        symbol: str,
    ) -> dict[
        str,
        Any,
    ]:

        ticker = (
            await self._okx
            .get_ticker(
                symbol
            )
        )

        last = (
            self.safe_float(
                ticker.last
            )
        )

        open_24h = (
            self.safe_float(
                ticker.open_24h
            )
        )

        high_24h = (
            self.safe_float(
                ticker.high_24h
            )
        )

        low_24h = (
            self.safe_float(
                ticker.low_24h
            )
        )

        volume_24h = (
            self.safe_float(
                ticker.volume_24h
            )
        )

        volume_ccy_24h = (
            self.safe_float(
                ticker
                .volume_currency_24h
            )
        )

        data: dict[
            str,
            Any,
        ] = {
            "symbol":
                symbol,

            "last":
                last,

            "open_24h":
                open_24h,

            "high_24h":
                high_24h,

            "low_24h":
                low_24h,

            "volume_24h":
                volume_24h,

            "volume_currency_24h":
                volume_ccy_24h,

            "timestamp":
                ticker
                .timestamp
                .isoformat(),

            "source":
                "OKX",
        }

        if (
            last is not None
            and open_24h is not None
            and open_24h != 0
        ):

            data[
                "price_change_pct"
            ] = (
                (
                    last
                    -
                    open_24h
                )
                /
                open_24h
                *
                100
            )

        if (
            high_24h is not None
            and low_24h is not None
            and last is not None
            and last != 0
        ):

            data[
                "range_pct"
            ] = (
                (
                    high_24h
                    -
                    low_24h
                )
                /
                last
                *
                100
            )

        return data

    # =================================
    # Liquidations
    # =================================

    async def _fetch_liquidations(
        self,
        instrument_family: str,
    ) -> dict[
        str,
        Any,
    ]:
        """
        OKX liquidation orders。

        Analyzer 目前只使用：

            long / short liquidation
            imbalance

        因此這裡主要聚合 liquidation
        quantity。

        注意：

        FUTURES / SWAP sz 的原始單位
        是 contract。

        在沒有 contract-value normalization
        的情況下，這裡不宣稱是精確 USD
        notional。

        對同一 instrument family 做
        long-vs-short imbalance 時仍具有
        positioning 參考價值。
        """

        rows = await self._raw_get(
            self.LIQUIDATION_ENDPOINT,

            {
                "instType":
                    "SWAP",

                "instFamily":
                    instrument_family,

                "state":
                    "filled",

                "limit":
                    str(
                        self.config
                        .liquidation_limit
                    ),
            },
        )

        long_total = 0.0

        short_total = 0.0

        event_count = 0

        latest_timestamp: int | None = (
            None
        )

        for item in rows:

            if not isinstance(
                item,
                dict,
            ):

                continue

            details = (
                item.get(
                    "details"
                )
            )

            if not isinstance(
                details,
                list,
            ):

                # 保留對可能 flat
                # response 的相容性。
                details = [
                    item
                ]

            for detail in details:

                if not isinstance(
                    detail,
                    dict,
                ):

                    continue

                size = (
                    self.safe_float(
                        detail.get(
                            "sz"
                        )
                    )
                )

                if (
                    size is None
                    or size <= 0
                ):

                    continue

                pos_side = str(
                    detail.get(
                        "posSide",
                        "",
                    )
                ).strip().lower()

                order_side = str(
                    detail.get(
                        "side",
                        "",
                    )
                ).strip().lower()

                # Hedge mode:
                #
                # posSide 可直接辨識
                # 被清算的是 long / short。
                #
                # Net mode：
                #
                # sell liquidation
                # 通常代表 long 被清算；
                #
                # buy liquidation
                # 通常代表 short 被清算。
                if pos_side == "long":

                    long_total += (
                        size
                    )

                elif pos_side == "short":

                    short_total += (
                        size
                    )

                elif order_side == "sell":

                    long_total += (
                        size
                    )

                elif order_side == "buy":

                    short_total += (
                        size
                    )

                else:

                    continue

                event_count += 1

                timestamp = (
                    self._extract_timestamp(
                        detail
                    )
                )

                if timestamp is None:

                    timestamp = (
                        self._extract_timestamp(
                            item
                        )
                    )

                if (
                    timestamp is not None
                    and (
                        latest_timestamp
                        is None
                        or timestamp
                        >
                        latest_timestamp
                    )
                ):

                    latest_timestamp = (
                        timestamp
                    )

        if event_count == 0:

            return {}

        data: dict[
            str,
            Any,
        ] = {
            "long_liquidations":
                long_total,

            "short_liquidations":
                short_total,

            "event_count":
                event_count,

            "unit":
                "contracts",

            "instrument_family":
                instrument_family,

            "source":
                "OKX",
        }

        if (
            latest_timestamp
            is not None
        ):

            data[
                "timestamp"
            ] = (
                self._ms_to_iso(
                    latest_timestamp
                )
            )

        return data

    # =================================
    # Raw OKX public HTTP
    # =================================

    async def _raw_get(
        self,
        endpoint: str,
        params: dict[
            str,
            Any,
        ],
    ) -> list[
        Any
    ]:

        clean_params = {
            key:
                value

            for (
                key,
                value,
            )
            in params.items()

            if value is not None
        }

        last_error: Exception | None = (
            None
        )

        for attempt in range(
            1,
            self.config
            .max_retries
            +
            1,
        ):

            try:

                response = (
                    await self._http.get(
                        endpoint,
                        params=(
                            clean_params
                        ),
                    )
                )

                if (
                    response.status_code
                    ==
                    429
                    or
                    response.status_code
                    >=
                    500
                ):

                    raise httpx.HTTPStatusError(
                        (
                            "Retryable OKX "
                            f"HTTP status "
                            f"{response.status_code}"
                        ),
                        request=(
                            response.request
                        ),
                        response=response,
                    )

                response.raise_for_status()

                payload = (
                    response.json()
                )

                if not isinstance(
                    payload,
                    dict,
                ):

                    raise ValueError(
                        (
                            "Invalid OKX "
                            "response payload."
                        )
                    )

                code = str(
                    payload.get(
                        "code",
                        "",
                    )
                )

                if code != "0":

                    raise RuntimeError(
                        (
                            f"OKX API "
                            f"{code}: "
                            f"{payload.get('msg')}"
                        )
                    )

                data = (
                    payload.get(
                        "data"
                    )
                )

                if not isinstance(
                    data,
                    list,
                ):

                    raise ValueError(
                        (
                            "OKX response "
                            "'data' is not "
                            "a list."
                        )
                    )

                return data

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            ) as exc:

                last_error = exc

                if (
                    attempt
                    >=
                    self.config
                    .max_retries
                ):

                    break

                await asyncio.sleep(
                    self.config
                    .retry_delay_seconds
                    *
                    attempt
                )

            except Exception:

                # API logical errors
                # 不做無意義 retry。
                raise

        raise RuntimeError(
            (
                "OKX sentiment request "
                "failed after "
                f"{self.config.max_retries} "
                "attempts: "
                f"{last_error}"
            )
        )

    # =================================
    # Rubik parsers
    # =================================

    def _parse_long_short_point(
        self,
        row: Any,
    ) -> tuple[
        int,
        float,
    ] | None:
        """
        OKX Rubik endpoints
        歷史上主要使用 array rows：

            [
                timestamp,
                ratio
            ]

        同時支援 dict，
        避免 response format
        小改動直接破壞 pipeline。
        """

        if isinstance(
            row,
            (
                list,
                tuple,
            ),
        ):

            if len(row) < 2:

                return None

            timestamp = (
                self._to_int(
                    row[0]
                )
            )

            ratio = (
                self.safe_float(
                    row[1]
                )
            )

        elif isinstance(
            row,
            dict,
        ):

            timestamp = (
                self._extract_timestamp(
                    row
                )
            )

            ratio = (
                self._first_float(
                    row,
                    (
                        "ratio",
                        "longShortRatio",
                        "long_short_ratio",
                    ),
                )
            )

        else:

            return None

        if (
            timestamp is None
            or ratio is None
            or ratio <= 0
        ):

            return None

        return (
            timestamp,
            ratio,
        )

    def _parse_oi_point(
        self,
        row: Any,
    ) -> tuple[
        int,
        float,
        float | None,
    ] | None:
        """
        Rubik OI/Volume：

            [
                timestamp,
                open_interest,
                volume
            ]

        同樣保留 dict fallback。
        """

        if isinstance(
            row,
            (
                list,
                tuple,
            ),
        ):

            if len(row) < 2:

                return None

            timestamp = (
                self._to_int(
                    row[0]
                )
            )

            open_interest = (
                self.safe_float(
                    row[1]
                )
            )

            volume = (
                self.safe_float(
                    row[2]
                )
                if len(row) >= 3
                else None
            )

        elif isinstance(
            row,
            dict,
        ):

            timestamp = (
                self._extract_timestamp(
                    row
                )
            )

            open_interest = (
                self._first_float(
                    row,
                    (
                        "openInterest",
                        "open_interest",
                        "oi",
                    ),
                )
            )

            volume = (
                self._first_float(
                    row,
                    (
                        "volume",
                        "vol",
                    ),
                )
            )

        else:

            return None

        if (
            timestamp is None
            or open_interest is None
        ):

            return None

        return (
            timestamp,
            open_interest,
            volume,
        )

    # =================================
    # Generic helpers
    # =================================

    @classmethod
    def _first_float(
        cls,
        data: dict[
            str,
            Any,
        ],
        keys: tuple[
            str,
            ...,
        ],
    ) -> float | None:

        for key in keys:

            if key not in data:

                continue

            value = (
                cls.safe_float(
                    data.get(
                        key
                    )
                )
            )

            if value is not None:

                return value

        return None

    @staticmethod
    def _to_int(
        value: Any,
    ) -> int | None:

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @classmethod
    def _extract_timestamp(
        cls,
        data: dict[
            str,
            Any,
        ],
    ) -> int | None:

        for key in (
            "ts",
            "timestamp",
            "time",
            "uTime",
        ):

            if key not in data:

                continue

            timestamp = (
                cls._to_int(
                    data.get(
                        key
                    )
                )
            )

            if timestamp is not None:

                return timestamp

        return None

    @staticmethod
    def _ms_to_iso(
        timestamp_ms: int,
    ) -> str:

        return (
            datetime.fromtimestamp(
                timestamp_ms
                /
                1000,
                tz=timezone.utc,
            )
            .isoformat()
        )
