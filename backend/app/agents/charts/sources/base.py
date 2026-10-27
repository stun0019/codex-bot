from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from ...models import (
    MarketContext,
)

from ..models import (
    ChartsInput,
)


@dataclass(slots=True)
class ChartsSourceConfig:
    """
    CHARTS Source 共用設定。

    Source 責任：

        External OHLCV
            ↓
        Normalization
            ↓
        ChartsInput

    Source 不負責：

        - EMA / RSI / MACD
        - Market structure
        - Technical bias
        - Trade decision
    """

    name: str = "charts_source"

    enabled: bool = True

    timeout_seconds: float = 15.0

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.name = (
            self.name
            .strip()
        )

        if not self.name:

            raise ValueError(
                "Charts source name "
                "cannot be empty."
            )

        if (
            self.timeout_seconds
            <= 0
        ):

            raise ValueError(
                "timeout_seconds must "
                "be greater than 0."
            )


@dataclass(slots=True)
class ChartsSourceResult:
    """
    單一 CHARTS Source
    抓取結果。

    payload：

        可直接餵給：

            ChartsAgent

    errors：

        individual timeframe
        partial failure。

    metadata：

        Service / logging /
        dashboard 使用。
    """

    source: str

    payload: ChartsInput = field(
        default_factory=(
            ChartsInput
        )
    )

    errors: list[
        str
    ] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    fetched_at: datetime = field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )

    @property
    def success(
        self,
    ) -> bool:
        """
        至少一個 timeframe
        有 candle data 即視為成功。
        """

        return (
            self.has_payload_data(
                self.payload
            )
        )

    @staticmethod
    def has_payload_data(
        payload: ChartsInput,
    ) -> bool:

        return any(
            bool(candles)
            for candles
            in payload
            .candles
            .values()
        )


class BaseChartsSource(
    ABC
):
    """
    CHARTS Source 抽象基底。

    Pipeline：

        Exchange / Database
                ↓
        BaseChartsSource
                ↓
        ChartsSourceResult
                ↓
        ChartsInput
                ↓
        ChartsAnalyzer
    """

    def __init__(
        self,
        config: ChartsSourceConfig,
    ) -> None:

        self.config = config

        self._closed = False

    @property
    def name(
        self,
    ) -> str:

        return (
            self.config.name
        )

    @property
    def enabled(
        self,
    ) -> bool:

        return (
            self.config.enabled
        )

    @property
    def closed(
        self,
    ) -> bool:

        return (
            self._closed
        )

    async def __aenter__(
        self,
    ) -> "BaseChartsSource":

        if self._closed:

            raise RuntimeError(
                (
                    f"Charts source "
                    f"'{self.name}' "
                    f"is already closed."
                )
            )

        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:

        await self.close()

    @abstractmethod
    async def fetch(
        self,
        context: MarketContext,
    ) -> ChartsSourceResult:
        """
        抓取 chart data。

        每個實際 source 必須實作。
        """

        raise NotImplementedError

    async def close(
        self,
    ) -> None:
        """
        Base source 沒有 external client，
        所以只標記 closed。

        子類別如果擁有：

            httpx client
            websocket
            database connection

        應 override close()，
        並最後呼叫：

            await super().close()
        """

        self._closed = True

    def ensure_available(
        self,
    ) -> None:
        """
        fetch 前檢查 source 狀態。
        """

        if not self.enabled:

            raise RuntimeError(
                (
                    f"Charts source "
                    f"'{self.name}' "
                    f"is disabled."
                )
            )

        if self.closed:

            raise RuntimeError(
                (
                    f"Charts source "
                    f"'{self.name}' "
                    f"is already closed."
                )
            )

    # =================================
    # Symbol
    # =================================

    @staticmethod
    def normalize_symbol(
        symbol: str,
    ) -> str:
        """
        Symbol 統一：

            btc-usdt-swap
                ↓
            BTC-USDT-SWAP
        """

        normalized = (
            symbol
            .strip()
            .upper()
        )

        if not normalized:

            raise ValueError(
                "Market symbol "
                "cannot be empty."
            )

        return normalized

    # =================================
    # Timeframe
    # =================================

    @staticmethod
    def normalize_timeframe(
        timeframe: str,
    ) -> str:
        """
        統一 CHARTS timeframe。

        核心規則：

            小寫 m = minute
            大寫 M = month

        所以：

            1m  = 1 minute
            3m  = 3 minutes
            5m  = 5 minutes
            15m = 15 minutes
            30m = 30 minutes

            1H  = 1 hour
            2H  = 2 hours
            4H  = 4 hours
            6H  = 6 hours
            12H = 12 hours

            1D  = 1 day
            2D  = 2 days
            3D  = 3 days

            1W  = 1 week

            1M  = 1 month
            3M  = 3 months

        注意：

            不可以直接 timeframe.upper()

        因為：

            "1m".upper()
                ==
            "1M"

        會造成 minute / month collision。
        """

        value = (
            timeframe
            .strip()
        )

        if not value:

            raise ValueError(
                "Timeframe cannot "
                "be empty."
            )

        # =============================
        # Minutes
        # =============================
        #
        # m 必須是小寫。
        #
        # 1m
        # 3m
        # 5m
        # 15m
        # 30m
        #

        if value.endswith(
            "m"
        ):

            number = (
                value[:-1]
            )

            if number.isdigit():

                normalized = (
                    f"{int(number)}m"
                )

                supported = {
                    "1m",
                    "3m",
                    "5m",
                    "15m",
                    "30m",
                }

                if (
                    normalized
                    in supported
                ):

                    return normalized

        # =============================
        # Months
        # =============================
        #
        # M 必須是大寫。
        #
        # 1M
        # 3M
        #

        if value.endswith(
            "M"
        ):

            number = (
                value[:-1]
            )

            if number.isdigit():

                normalized = (
                    f"{int(number)}M"
                )

                supported = {
                    "1M",
                    "3M",
                }

                if (
                    normalized
                    in supported
                ):

                    return normalized

        # =============================
        # Hours
        # =============================
        #
        # 接受：
        #
        # 1H
        # 1h
        #
        # 統一輸出：
        #
        # 1H
        #

        if (
            value.endswith("H")
            or value.endswith("h")
        ):

            number = (
                value[:-1]
            )

            if number.isdigit():

                normalized = (
                    f"{int(number)}H"
                )

                supported = {
                    "1H",
                    "2H",
                    "4H",
                    "6H",
                    "12H",
                }

                if (
                    normalized
                    in supported
                ):

                    return normalized

        # =============================
        # Days
        # =============================

        if (
            value.endswith("D")
            or value.endswith("d")
        ):

            number = (
                value[:-1]
            )

            if number.isdigit():

                normalized = (
                    f"{int(number)}D"
                )

                supported = {
                    "1D",
                    "2D",
                    "3D",
                }

                if (
                    normalized
                    in supported
                ):

                    return normalized

        # =============================
        # Weeks
        # =============================

        if (
            value.endswith("W")
            or value.endswith("w")
        ):

            number = (
                value[:-1]
            )

            if number.isdigit():

                normalized = (
                    f"{int(number)}W"
                )

                supported = {
                    "1W",
                }

                if (
                    normalized
                    in supported
                ):

                    return normalized

        raise ValueError(
            (
                "Unsupported timeframe: "
                f"{timeframe!r}. "
                "Supported formats: "
                "1m, 3m, 5m, 15m, 30m, "
                "1H, 2H, 4H, 6H, 12H, "
                "1D, 2D, 3D, "
                "1W, "
                "1M, 3M. "
                "Lowercase 'm' means "
                "minutes; uppercase 'M' "
                "means months."
            )
        )

    @classmethod
    def normalize_timeframes(
        cls,
        timeframes: list[
            str
        ],
    ) -> list[
        str
    ]:
        """
        Normalize + 去重。

        保留原始順序。

        Example：

            [
                "15m",
                "1h",
                "4H",
                "15m",
                "1M",
            ]

                ↓

            [
                "15m",
                "1H",
                "4H",
                "1M",
            ]
        """

        result: list[
            str
        ] = []

        seen: set[
            str
        ] = set()

        for timeframe in timeframes:

            normalized = (
                cls.normalize_timeframe(
                    timeframe
                )
            )

            if (
                normalized
                in seen
            ):

                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return result
