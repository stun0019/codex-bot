from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx

from .constants import (
    Bar,
    InstrumentType,
    OKX_REST_BASE_URL,
)
from .exceptions import (
    OKXAPIError,
    OKXDataError,
    OKXRequestError,
)
from .models import (
    Candle,
    FundingRate,
    Instrument,
    OpenInterest,
    OrderBook,
    OrderBookLevel,
    Ticker,
    ms_to_datetime,
    optional_decimal,
)


class OKXPublicClient:
    """
    OKX 公開市場資料 Client。

    此 Client：
    - 不需要 API Key
    - 不包含交易功能
    - 不包含提款功能
    - 不包含私人帳戶功能
    """

    def __init__(
        self,
        base_url: str = OKX_REST_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "codex-bot/1.0",
            },
        )

    async def __aenter__(
        self,
    ) -> "OKXPublicClient":
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
        await self._client.aclose()

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:

        clean_params = {
            key: value
            for key, value in (
                params or {}
            ).items()
            if value is not None
        }

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.max_retries + 1,
        ):
            try:
                response = await self._client.get(
                    endpoint,
                    params=clean_params,
                )

                if response.status_code >= 500:
                    raise OKXRequestError(
                        f"OKX server returned "
                        f"{response.status_code}"
                    )

                response.raise_for_status()

                payload = response.json()

                code = str(
                    payload.get(
                        "code",
                        "",
                    )
                )

                if code != "0":
                    raise OKXAPIError(
                        code=code,
                        message=str(
                            payload.get(
                                "msg",
                                "Unknown OKX error",
                            )
                        ),
                    )

                data = payload.get("data")

                if not isinstance(
                    data,
                    list,
                ):
                    raise OKXDataError(
                        "OKX response 'data' "
                        "is not a list."
                    )

                return data

            except OKXAPIError:
                raise

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
                OKXRequestError,
            ) as exc:

                last_error = exc

                if attempt >= self.max_retries:
                    break

                await asyncio.sleep(
                    0.5 * attempt
                )

        raise OKXRequestError(
            f"OKX request failed after "
            f"{self.max_retries} attempts: "
            f"{last_error}"
        )

    async def get_instruments(
        self,
        inst_type: InstrumentType,
        inst_id: str | None = None,
    ) -> list[Instrument]:

        data = await self._get(
            "/api/v5/public/instruments",
            {
                "instType": inst_type.value,
                "instId": inst_id,
            },
        )

        result: list[Instrument] = []

        for item in data:
            result.append(
                Instrument(
                    inst_type=item.get(
                        "instType",
                        "",
                    ),
                    inst_id=item.get(
                        "instId",
                        "",
                    ),
                    state=item.get("state"),
                    base_ccy=item.get(
                        "baseCcy"
                    )
                    or None,
                    quote_ccy=item.get(
                        "quoteCcy"
                    )
                    or None,
                    settle_ccy=item.get(
                        "settleCcy"
                    )
                    or None,
                    contract_value=optional_decimal(
                        item.get("ctVal")
                    ),
                    tick_size=optional_decimal(
                        item.get("tickSz")
                    ),
                    lot_size=optional_decimal(
                        item.get("lotSz")
                    ),
                    min_size=optional_decimal(
                        item.get("minSz")
                    ),
                    raw=item,
                )
            )

        return result

    async def get_ticker(
        self,
        inst_id: str,
    ) -> Ticker:

        data = await self._get(
            "/api/v5/market/ticker",
            {
                "instId": inst_id,
            },
        )

        if not data:
            raise OKXDataError(
                f"No ticker returned for "
                f"{inst_id}"
            )

        item = data[0]

        return self._parse_ticker(
            item
        )

    async def get_tickers(
        self,
        inst_type: InstrumentType,
    ) -> list[Ticker]:

        data = await self._get(
            "/api/v5/market/tickers",
            {
                "instType": inst_type.value,
            },
        )

        return [
            self._parse_ticker(item)
            for item in data
        ]

    async def get_candles(
        self,
        inst_id: str,
        bar: Bar,
        limit: int = 100,
    ) -> list[Candle]:

        if not 1 <= limit <= 300:
            raise ValueError(
                "limit must be between "
                "1 and 300"
            )

        data = await self._get(
            "/api/v5/market/candles",
            {
                "instId": inst_id,
                "bar": bar.value,
                "limit": str(limit),
            },
        )

        candles = [
            self._parse_candle(item)
            for item in data
        ]

        candles.sort(
            key=lambda candle:
            candle.timestamp
        )

        return candles

    async def get_history_candles(
        self,
        inst_id: str,
        bar: Bar,
        limit: int = 100,
        after: str | None = None,
        before: str | None = None,
    ) -> list[Candle]:

        if not 1 <= limit <= 100:
            raise ValueError(
                "Historical candle limit "
                "must be between 1 and 100"
            )

        data = await self._get(
            "/api/v5/market/history-candles",
            {
                "instId": inst_id,
                "bar": bar.value,
                "limit": str(limit),
                "after": after,
                "before": before,
            },
        )

        candles = [
            self._parse_candle(item)
            for item in data
        ]

        candles.sort(
            key=lambda candle:
            candle.timestamp
        )

        return candles

    async def get_order_book(
        self,
        inst_id: str,
        size: int = 50,
    ) -> OrderBook:

        if not 1 <= size <= 400:
            raise ValueError(
                "Order book size must be "
                "between 1 and 400"
            )

        data = await self._get(
            "/api/v5/market/books",
            {
                "instId": inst_id,
                "sz": str(size),
            },
        )

        if not data:
            raise OKXDataError(
                f"No order book returned "
                f"for {inst_id}"
            )

        item = data[0]

        return OrderBook(
            inst_id=inst_id,
            bids=[
                self._parse_order_book_level(
                    level
                )
                for level in item.get(
                    "bids",
                    [],
                )
            ],
            asks=[
                self._parse_order_book_level(
                    level
                )
                for level in item.get(
                    "asks",
                    [],
                )
            ],
            timestamp=ms_to_datetime(
                item["ts"]
            ),
            sequence_id=(
                int(item["seqId"])
                if item.get("seqId")
                not in (
                    None,
                    "",
                )
                else None
            ),
        )

    async def get_funding_rate(
        self,
        inst_id: str,
    ) -> FundingRate:

        data = await self._get(
            "/api/v5/public/funding-rate",
            {
                "instId": inst_id,
            },
        )

        if not data:
            raise OKXDataError(
                f"No funding rate returned "
                f"for {inst_id}"
            )

        item = data[0]

        return FundingRate(
            inst_id=item.get(
                "instId",
                inst_id,
            ),
            funding_rate=optional_decimal(
                item.get("fundingRate")
            ),
            funding_time=(
                ms_to_datetime(
                    item["fundingTime"]
                )
                if item.get("fundingTime")
                else None
            ),
            next_funding_time=(
                ms_to_datetime(
                    item["nextFundingTime"]
                )
                if item.get(
                    "nextFundingTime"
                )
                else None
            ),
            min_funding_rate=optional_decimal(
                item.get(
                    "minFundingRate"
                )
            ),
            max_funding_rate=optional_decimal(
                item.get(
                    "maxFundingRate"
                )
            ),
        )

    async def get_open_interest(
        self,
        inst_type: InstrumentType,
        inst_id: str | None = None,
    ) -> list[OpenInterest]:

        data = await self._get(
            "/api/v5/public/open-interest",
            {
                "instType": inst_type.value,
                "instId": inst_id,
            },
        )

        return [
            OpenInterest(
                inst_type=item.get(
                    "instType",
                    "",
                ),
                inst_id=item.get(
                    "instId",
                    "",
                ),
                open_interest=Decimal(
                    item["oi"]
                ),
                open_interest_ccy=(
                    optional_decimal(
                        item.get("oiCcy")
                    )
                ),
                open_interest_usd=(
                    optional_decimal(
                        item.get("oiUsd")
                    )
                ),
                timestamp=ms_to_datetime(
                    item["ts"]
                ),
            )
            for item in data
        ]

    @staticmethod
    def _parse_ticker(
        item: dict[str, Any],
    ) -> Ticker:

        return Ticker(
            inst_type=item.get(
                "instType",
                "",
            ),
            inst_id=item["instId"],
            last=Decimal(
                item["last"]
            ),
            last_size=optional_decimal(
                item.get("lastSz")
            ),
            ask_price=optional_decimal(
                item.get("askPx")
            ),
            ask_size=optional_decimal(
                item.get("askSz")
            ),
            bid_price=optional_decimal(
                item.get("bidPx")
            ),
            bid_size=optional_decimal(
                item.get("bidSz")
            ),
            open_24h=optional_decimal(
                item.get("open24h")
            ),
            high_24h=optional_decimal(
                item.get("high24h")
            ),
            low_24h=optional_decimal(
                item.get("low24h")
            ),
            volume_24h=optional_decimal(
                item.get("vol24h")
            ),
            volume_currency_24h=(
                optional_decimal(
                    item.get("volCcy24h")
                )
            ),
            timestamp=ms_to_datetime(
                item["ts"]
            ),
        )

    @staticmethod
    def _parse_candle(
        item: list[Any],
    ) -> Candle:

        if len(item) < 9:
            raise OKXDataError(
                "Invalid OKX candle format."
            )

        return Candle(
            timestamp=ms_to_datetime(
                item[0]
            ),
            open=Decimal(item[1]),
            high=Decimal(item[2]),
            low=Decimal(item[3]),
            close=Decimal(item[4]),
            volume=Decimal(item[5]),
            volume_currency=(
                optional_decimal(
                    item[6]
                )
            ),
            volume_quote=(
                optional_decimal(
                    item[7]
                )
            ),
            confirmed=(
                str(item[8]) == "1"
            ),
        )

    @staticmethod
    def _parse_order_book_level(
        item: list[Any],
    ) -> OrderBookLevel:

        if len(item) < 2:
            raise OKXDataError(
                "Invalid order book level."
            )

        return OrderBookLevel(
            price=Decimal(item[0]),
            size=Decimal(item[1]),
            order_count=(
                int(item[3])
                if len(item) >= 4
                and item[3] != ""
                else None
            ),
        )
