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

        return self._closed

    async def __aenter__(
        self,
    ) -> "BaseChartsSource":

        self._closed = False

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
        """

        raise NotImplementedError

    async def close(
        self,
    ) -> None:

        self._closed = True

    def ensure_available(
        self,
    ) -> None:

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

    @staticmethod
    def normalize_symbol(
        symbol: str,
    ) -> str:

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

    @staticmethod
    def normalize_timeframe(
        timeframe: str,
    ) -> str:

        value = (
            timeframe
            .strip()
        )

        if not value:

            raise ValueError(
                "Timeframe cannot "
                "be empty."
            )

        aliases = {
            "1M":
                "1m",

            "3M":
                "3m",

            "5M":
                "5m",

            "15M":
                "15m",

            "30M":
                "30m",

            "1H":
                "1H",

            "2H":
                "2H",

            "4H":
                "4H",

            "6H":
                "6H",

            "12H":
                "12H",

            "1D":
                "1D",

            "2D":
                "2D",

            "3D":
                "3D",

            "1W":
                "1W",

            "1MO":
                "1M",

            "3MO":
                "3M",
        }

        upper = (
            value.upper()
        )

        return (
            aliases.get(
                upper,
                value,
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
        Normalize + 去重，
        保留原始順序。
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

            if normalized in seen:

                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return result
