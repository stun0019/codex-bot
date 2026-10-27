from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any

from ...exchanges.okx import (
    InstrumentType,
    OKXPublicClient,
    Ticker,
)
from .models import ScoutCandidate


@dataclass(slots=True)
class ScoutScanConfig:
    """
    SCOUT 市場掃描設定。

    此設定只控制市場掃描行為，
    不代表任何固定交易策略。
    """

    quote_currency: str = "USDT"

    top_n: int = 10

    detail_pool_size: int = 40

    max_concurrency: int = 8

    require_live: bool = True


@dataclass(slots=True)
class _MarketRow:
    """
    Scanner 內部市場資料模型。
    """

    symbol: str

    last_price: float

    open_24h: float | None
    high_24h: float | None
    low_24h: float | None

    bid_price: float | None
    ask_price: float | None

    volume_24h: float
    quote_volume_24h: float

    price_change_pct: float
    abs_price_change_pct: float

    range_pct: float

    spread_pct: float | None = None

    funding_rate: float | None = None

    open_interest: float | None = None
    open_interest_usd: float | None = None

    volume_score: float = 0.0
    volatility_score: float = 0.0
    activity_score: float = 0.0
    liquidity_score: float = 0.0
    open_interest_score: float = 0.0

    preliminary_score: float = 0.0
    final_score: float = 0.0


class ScoutScanner:
    """
    OKX 市場機會掃描器。

    功能：

    1. 取得 OKX SWAP 市場
    2. 篩選 USDT 永續合約
    3. 取得 Ticker
    4. 分析市場活躍度
    5. 分析成交量
    6. 分析波動
    7. 分析流動性
    8. 取得 Funding Rate
    9. 取得 Open Interest
    10. 建立市場機會排名

    Scout Score 代表：

        市場目前是否值得進一步分析

    不代表：

        LONG
        SHORT
        勝率
        交易策略訊號

    多空方向由後續 Agent 分析：

        NEWS
        SENTIMENT
        CHARTS
        RISK
        DECISION
    """

    def __init__(
        self,
        client: OKXPublicClient | None = None,
        config: ScoutScanConfig | None = None,
    ) -> None:

        self.client = (
            client
            if client is not None
            else OKXPublicClient()
        )

        self.config = (
            config
            if config is not None
            else ScoutScanConfig()
        )

        self._owns_client = (
            client is None
        )

        self._semaphore = asyncio.Semaphore(
            self.config.max_concurrency
        )

    async def __aenter__(
        self,
    ) -> "ScoutScanner":

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
        """
        關閉 Scanner。

        如果 OKX Client 是 Scanner 自己建立，
        則一起關閉 HTTP Client。
        """

        if self._owns_client:
            await self.client.close()

    async def scan(
        self,
        symbols: list[str] | None = None,
        top_n: int | None = None,
    ) -> list[ScoutCandidate]:
        """
        執行完整市場掃描。

        symbols:

            None
                掃描全部 USDT-SWAP

            ["BTC-USDT-SWAP", ...]
                只掃描指定市場

        top_n:

            最終輸出的候選數量
        """

        limit = (
            top_n
            if top_n is not None
            else self.config.top_n
        )

        if limit <= 0:
            return []

        allowed_symbols = (
            {
                symbol.upper()
                for symbol in symbols
            }
            if symbols
            else None
        )

        instruments_task = (
            self.client.get_instruments(
                InstrumentType.SWAP
            )
        )

        tickers_task = (
            self.client.get_tickers(
                InstrumentType.SWAP
            )
        )

        instruments, tickers = (
            await asyncio.gather(
                instruments_task,
                tickers_task,
            )
        )

        valid_symbols: set[str] = set()

        for instrument in instruments:

            if (
                self.config.require_live
                and instrument.state != "live"
            ):
                continue

            symbol = (
                instrument.inst_id.upper()
            )

            if not self._is_target_symbol(
                symbol=symbol,
                settle_ccy=instrument.settle_ccy,
            ):
                continue

            if (
                allowed_symbols is not None
                and symbol not in allowed_symbols
            ):
                continue

            valid_symbols.add(
                symbol
            )

        ticker_map = {
            ticker.inst_id.upper(): ticker
            for ticker in tickers
        }

        rows: list[_MarketRow] = []

        for symbol in valid_symbols:

            ticker = ticker_map.get(
                symbol
            )

            if ticker is None:
                continue

            row = self._ticker_to_row(
                ticker
            )

            if row is None:
                continue

            rows.append(
                row
            )

        if not rows:
            return []

        self._calculate_preliminary_scores(
            rows
        )

        rows.sort(
            key=lambda item:
                item.preliminary_score,
            reverse=True,
        )

        detail_pool_size = max(
            limit,
            self.config.detail_pool_size,
        )

        detail_pool_size = min(
            detail_pool_size,
            len(rows),
        )

        detail_rows = rows[
            :detail_pool_size
        ]

        await asyncio.gather(
            *[
                self._load_details(
                    row
                )
                for row in detail_rows
            ]
        )

        self._calculate_final_scores(
            detail_rows
        )

        detail_rows.sort(
            key=lambda item:
                item.final_score,
            reverse=True,
        )

        return [
            self._to_candidate(
                row
            )
            for row in detail_rows[
                :limit
            ]
        ]

    def _is_target_symbol(
        self,
        symbol: str,
        settle_ccy: str | None,
    ) -> bool:
        """
        判斷是否屬於 Scanner 掃描市場。

        預設掃描：

            *-USDT-SWAP
        """

        quote = (
            self.config
            .quote_currency
            .upper()
        )

        expected_suffix = (
            f"-{quote}-SWAP"
        )

        if not symbol.endswith(
            expected_suffix
        ):
            return False

        if (
            settle_ccy
            and settle_ccy.upper()
            != quote
        ):
            return False

        return True

    def _ticker_to_row(
        self,
        ticker: Ticker,
    ) -> _MarketRow | None:
        """
        將 OKX Ticker
        轉換為 Scanner 內部資料。
        """

        last = self._to_float(
            ticker.last
        )

        if (
            last is None
            or last <= 0
        ):
            return None

        open_24h = self._to_float(
            ticker.open_24h
        )

        high_24h = self._to_float(
            ticker.high_24h
        )

        low_24h = self._to_float(
            ticker.low_24h
        )

        bid_price = self._to_float(
            ticker.bid_price
        )

        ask_price = self._to_float(
            ticker.ask_price
        )

        volume_24h = (
            self._to_float(
                ticker.volume_24h
            )
            or 0.0
        )

        volume_currency_24h = (
            self._to_float(
                ticker.volume_currency_24h
            )
            or 0.0
        )

        # 將 underlying currency volume
        # 乘上目前價格，
        # 建立近似 quote-value。
        #
        # 此數值主要用於不同市場之間
        # 的相對活躍度排名，
        # 不是交易所帳務數字。

        quote_volume_24h = (
            volume_currency_24h
            * last
        )

        if quote_volume_24h <= 0:
            quote_volume_24h = (
                volume_24h
            )

        price_change_pct = (
            self._percentage_change(
                current=last,
                reference=open_24h,
            )
        )

        range_pct = (
            self._range_percentage(
                high=high_24h,
                low=low_24h,
                reference=(
                    open_24h
                    or last
                ),
            )
        )

        spread_pct = (
            self._spread_percentage(
                bid=bid_price,
                ask=ask_price,
            )
        )

        return _MarketRow(
            symbol=(
                ticker.inst_id.upper()
            ),

            last_price=last,

            open_24h=open_24h,

            high_24h=high_24h,

            low_24h=low_24h,

            bid_price=bid_price,

            ask_price=ask_price,

            volume_24h=volume_24h,

            quote_volume_24h=(
                quote_volume_24h
            ),

            price_change_pct=(
                price_change_pct
            ),

            abs_price_change_pct=abs(
                price_change_pct
            ),

            range_pct=range_pct,

            spread_pct=spread_pct,
        )

    def _calculate_preliminary_scores(
        self,
        rows: list[_MarketRow],
    ) -> None:
        """
        第一階段快速排名。

        用全部 Ticker 資料先篩選市場。

        指標：

        Volume
        Volatility
        Activity

        這一階段不額外呼叫大量 API。
        """

        volume_scores = (
            self._rank_scores(
                {
                    row.symbol:
                        self._log_value(
                            row.quote_volume_24h
                        )
                    for row in rows
                }
            )
        )

        volatility_scores = (
            self._rank_scores(
                {
                    row.symbol:
                        row.range_pct
                    for row in rows
                }
            )
        )

        activity_scores = (
            self._rank_scores(
                {
                    row.symbol:
                        row.abs_price_change_pct
                    for row in rows
                }
            )
        )

        for row in rows:

            row.volume_score = (
                volume_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.volatility_score = (
                volatility_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.activity_score = (
                activity_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.preliminary_score = (
                (
                    row.volume_score
                    * 0.50
                )
                +
                (
                    row.volatility_score
                    * 0.30
                )
                +
                (
                    row.activity_score
                    * 0.20
                )
            )

    async def _load_details(
        self,
        row: _MarketRow,
    ) -> None:
        """
        對第一階段候選市場取得：

        Order Book
        Funding Rate
        Open Interest

        任一資料來源失敗，
        不會讓整個市場掃描中止。
        """

        async with self._semaphore:

            results = await asyncio.gather(
                self.client.get_order_book(
                    row.symbol,
                    size=5,
                ),

                self.client.get_funding_rate(
                    row.symbol
                ),

                self.client.get_open_interest(
                    InstrumentType.SWAP,
                    row.symbol,
                ),

                return_exceptions=True,
            )

        order_book_result = (
            results[0]
        )

        funding_result = (
            results[1]
        )

        open_interest_result = (
            results[2]
        )

        if not isinstance(
            order_book_result,
            BaseException,
        ):

            order_book = (
                order_book_result
            )

            if order_book.bids:

                row.bid_price = (
                    self._to_float(
                        order_book
                        .bids[0]
                        .price
                    )
                )

            if order_book.asks:

                row.ask_price = (
                    self._to_float(
                        order_book
                        .asks[0]
                        .price
                    )
                )

            row.spread_pct = (
                self._spread_percentage(
                    bid=row.bid_price,
                    ask=row.ask_price,
                )
            )

        if not isinstance(
            funding_result,
            BaseException,
        ):

            row.funding_rate = (
                self._to_float(
                    funding_result
                    .funding_rate
                )
            )

        if not isinstance(
            open_interest_result,
            BaseException,
        ):

            open_interest_items = (
                open_interest_result
            )

            item = next(
                (
                    value
                    for value
                    in open_interest_items
                    if (
                        value.inst_id.upper()
                        == row.symbol
                    )
                ),
                None,
            )

            if item is not None:

                row.open_interest = (
                    self._to_float(
                        item.open_interest
                    )
                )

                row.open_interest_usd = (
                    self._to_float(
                        item.open_interest_usd
                    )
                )

                if (
                    row.open_interest_usd
                    is None
                    and
                    item.open_interest_ccy
                    is not None
                ):

                    oi_ccy = (
                        self._to_float(
                            item.open_interest_ccy
                        )
                    )

                    if oi_ccy is not None:

                        row.open_interest_usd = (
                            oi_ccy
                            * row.last_price
                        )

    def _calculate_final_scores(
        self,
        rows: list[_MarketRow],
    ) -> None:
        """
        第二階段市場機會評分。

        Score 用途：

            判斷哪些市場值得交給
            後續 Agent 深入分析。

        Score 不代表多空方向。

        評估項目：

            Volume
            Liquidity
            Volatility
            Open Interest
            Activity

        Funding Rate 不直接決定
        Scout Score。

        Funding Rate 會保留給
        SENTIMENT Agent 分析。
        """

        if not rows:
            return

        volume_scores = (
            self._rank_scores(
                {
                    row.symbol:
                        self._log_value(
                            row.quote_volume_24h
                        )
                    for row in rows
                }
            )
        )

        volatility_scores = (
            self._rank_scores(
                {
                    row.symbol:
                        row.range_pct
                    for row in rows
                }
            )
        )

        activity_scores = (
            self._rank_scores(
                {
                    row.symbol:
                        row.abs_price_change_pct
                    for row in rows
                }
            )
        )

        spread_values = {
            row.symbol:
                row.spread_pct

            for row in rows

            if (
                row.spread_pct
                is not None
                and
                row.spread_pct >= 0
            )
        }

        liquidity_scores = (
            self._rank_scores(
                spread_values,
                higher_is_better=False,
            )
        )

        oi_values = {
            row.symbol:
                self._log_value(
                    row.open_interest_usd
                    or 0.0
                )

            for row in rows

            if (
                row.open_interest_usd
                is not None
                and
                row.open_interest_usd
                > 0
            )
        }

        open_interest_scores = (
            self._rank_scores(
                oi_values
            )
        )

        for row in rows:

            row.volume_score = (
                volume_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.volatility_score = (
                volatility_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.activity_score = (
                activity_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.liquidity_score = (
                liquidity_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            row.open_interest_score = (
                open_interest_scores.get(
                    row.symbol,
                    0.0,
                )
            )

            components: list[
                tuple[float, float]
            ] = []

            components.append(
                (
                    row.volume_score,
                    0.30,
                )
            )

            if (
                row.spread_pct
                is not None
            ):
                components.append(
                    (
                        row.liquidity_score,
                        0.25,
                    )
                )

            components.append(
                (
                    row.volatility_score,
                    0.20,
                )
            )

            if (
                row.open_interest_usd
                is not None
                and
                row.open_interest_usd
                > 0
            ):
                components.append(
                    (
                        row.open_interest_score,
                        0.15,
                    )
                )

            components.append(
                (
                    row.activity_score,
                    0.10,
                )
            )

            total_weight = sum(
                weight
                for _, weight
                in components
            )

            if total_weight <= 0:

                row.final_score = 0.0

                continue

            weighted_score = sum(
                score * weight
                for score, weight
                in components
            )

            row.final_score = (
                weighted_score
                / total_weight
            )

            row.final_score = max(
                0.0,
                min(
                    1.0,
                    row.final_score,
                ),
            )

    def _to_candidate(
        self,
        row: _MarketRow,
    ) -> ScoutCandidate:
        """
        將內部 Market Row
        轉為 ScoutCandidate。
        """

        reasons: list[str] = []

        if row.volume_score >= 0.75:

            reasons.append(
                "High relative 24H trading volume"
            )

        if row.liquidity_score >= 0.75:

            reasons.append(
                "Tight bid/ask spread"
            )

        if row.volatility_score >= 0.75:

            reasons.append(
                "Elevated 24H price range"
            )

        if row.activity_score >= 0.75:

            reasons.append(
                "Strong 24H price activity"
            )

        if (
            row.open_interest_score
            >= 0.75
        ):

            reasons.append(
                "High derivatives open interest"
            )

        if (
            row.funding_rate
            is not None
        ):

            funding_abs = abs(
                row.funding_rate
            )

            if funding_abs >= 0.0005:

                reasons.append(
                    "Notable funding-rate imbalance"
                )

        if not reasons:

            reasons.append(
                "Balanced market activity across scanner metrics"
            )

        metrics = {
            "last_price":
                row.last_price,

            "open_24h":
                row.open_24h,

            "high_24h":
                row.high_24h,

            "low_24h":
                row.low_24h,

            "price_change_pct":
                round(
                    row.price_change_pct,
                    6,
                ),

            "abs_price_change_pct":
                round(
                    row.abs_price_change_pct,
                    6,
                ),

            "range_pct":
                round(
                    row.range_pct,
                    6,
                ),

            "volume_24h":
                row.volume_24h,

            "approx_quote_volume_24h":
                row.quote_volume_24h,

            "bid_price":
                row.bid_price,

            "ask_price":
                row.ask_price,

            "spread_pct":
                (
                    round(
                        row.spread_pct,
                        8,
                    )
                    if (
                        row.spread_pct
                        is not None
                    )
                    else None
                ),

            "funding_rate":
                row.funding_rate,

            "open_interest":
                row.open_interest,

            "open_interest_usd":
                row.open_interest_usd,

            "scores": {
                "volume":
                    round(
                        row.volume_score,
                        4,
                    ),

                "liquidity":
                    round(
                        row.liquidity_score,
                        4,
                    ),

                "volatility":
                    round(
                        row.volatility_score,
                        4,
                    ),

                "open_interest":
                    round(
                        row.open_interest_score,
                        4,
                    ),

                "activity":
                    round(
                        row.activity_score,
                        4,
                    ),
            },
        }

        return ScoutCandidate(
            symbol=row.symbol,

            score=round(
                row.final_score,
                6,
            ),

            reasons=reasons,

            metrics=metrics,
        )

    @staticmethod
    def _rank_scores(
        values: dict[str, float],
        higher_is_better: bool = True,
    ) -> dict[str, float]:
        """
        將市場數值轉成 0 ~ 1 相對排名。

        不使用固定市場門檻，
        而是按照目前整體市場狀態
        做相對排名。
        """

        clean_values = {
            key: value

            for key, value
            in values.items()

            if math.isfinite(
                value
            )
        }

        if not clean_values:
            return {}

        unique_values = sorted(
            set(
                clean_values.values()
            )
        )

        if len(
            unique_values
        ) == 1:

            return {
                key: 0.5
                for key
                in clean_values
            }

        score_map: dict[
            float,
            float
        ] = {}

        denominator = (
            len(unique_values)
            - 1
        )

        for (
            index,
            value,
        ) in enumerate(
            unique_values
        ):

            score = (
                index
                / denominator
            )

            if not higher_is_better:

                score = (
                    1.0
                    - score
                )

            score_map[value] = (
                score
            )

        return {
            key:
                score_map[value]

            for key, value
            in clean_values.items()
        }

    @staticmethod
    def _percentage_change(
        current: float,
        reference: float | None,
    ) -> float:
        """
        計算價格百分比變化。

        例如：

            +5% = 5.0
            -5% = -5.0
        """

        if (
            reference is None
            or
            reference <= 0
        ):
            return 0.0

        return (
            (
                current
                - reference
            )
            / reference
        ) * 100.0

    @staticmethod
    def _range_percentage(
        high: float | None,
        low: float | None,
        reference: float | None,
    ) -> float:
        """
        計算 High-Low Range 百分比。
        """

        if (
            high is None
            or
            low is None
            or
            reference is None
            or
            reference <= 0
            or
            high < low
        ):
            return 0.0

        return (
            (
                high
                - low
            )
            / reference
        ) * 100.0

    @staticmethod
    def _spread_percentage(
        bid: float | None,
        ask: float | None,
    ) -> float | None:
        """
        計算 Bid / Ask Spread 百分比。

        Formula:

            spread =
                ask - bid

            midpoint =
                (ask + bid) / 2

            spread_pct =
                spread / midpoint * 100
        """

        if (
            bid is None
            or
            ask is None
            or
            bid <= 0
            or
            ask <= 0
            or
            ask < bid
        ):
            return None

        midpoint = (
            bid + ask
        ) / 2.0

        if midpoint <= 0:
            return None

        return (
            (
                ask
                - bid
            )
            / midpoint
        ) * 100.0

    @staticmethod
    def _log_value(
        value: float,
    ) -> float:
        """
        對大型數值做 log10 壓縮。

        用於：

            Volume
            Open Interest

        避免 BTC / ETH 等大型市場
        數值過大而完全壓過其他市場。
        """

        if (
            not math.isfinite(
                value
            )
            or
            value <= 0
        ):
            return 0.0

        return math.log10(
            1.0 + value
        )

    @staticmethod
    def _to_float(
        value: Any,
    ) -> float | None:
        """
        安全轉換：

            Decimal
            str
            int
            float

        →

            float
        """

        if value is None:
            return None

        try:

            result = float(
                value
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):

            return None

        if not math.isfinite(
            result
        ):
            return None

        return result
