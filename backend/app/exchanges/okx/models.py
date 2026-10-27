from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


def ms_to_datetime(
    timestamp_ms: str | int,
) -> datetime:
    return datetime.fromtimestamp(
        int(timestamp_ms) / 1000,
        tz=timezone.utc,
    )


def optional_decimal(
    value: Any,
) -> Decimal | None:
    if value in (
        None,
        "",
    ):
        return None

    return Decimal(str(value))


class Instrument(BaseModel):
    inst_type: str

    inst_id: str

    state: str | None = None

    base_ccy: str | None = None
    quote_ccy: str | None = None
    settle_ccy: str | None = None

    contract_value: Decimal | None = None

    tick_size: Decimal | None = None
    lot_size: Decimal | None = None
    min_size: Decimal | None = None

    raw: dict[str, Any] = Field(
        default_factory=dict
    )


class Ticker(BaseModel):
    inst_type: str

    inst_id: str

    last: Decimal

    last_size: Decimal | None = None

    ask_price: Decimal | None = None
    ask_size: Decimal | None = None

    bid_price: Decimal | None = None
    bid_size: Decimal | None = None

    open_24h: Decimal | None = None
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None

    volume_24h: Decimal | None = None
    volume_currency_24h: Decimal | None = None

    timestamp: datetime


class Candle(BaseModel):
    timestamp: datetime

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    volume: Decimal

    volume_currency: Decimal | None = None
    volume_quote: Decimal | None = None

    confirmed: bool


class OrderBookLevel(BaseModel):
    price: Decimal
    size: Decimal

    order_count: int | None = None


class OrderBook(BaseModel):
    inst_id: str

    bids: list[OrderBookLevel] = Field(
        default_factory=list
    )

    asks: list[OrderBookLevel] = Field(
        default_factory=list
    )

    timestamp: datetime

    sequence_id: int | None = None


class FundingRate(BaseModel):
    inst_id: str

    funding_rate: Decimal | None = None

    funding_time: datetime | None = None

    next_funding_time: datetime | None = None

    min_funding_rate: Decimal | None = None
    max_funding_rate: Decimal | None = None


class OpenInterest(BaseModel):
    inst_type: str

    inst_id: str

    open_interest: Decimal

    open_interest_ccy: Decimal | None = None
    open_interest_usd: Decimal | None = None

    timestamp: datetime
