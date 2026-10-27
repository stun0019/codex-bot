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
    SentimentInput,
)


@dataclass(slots=True)
class SentimentSourceConfig:
    """
    所有 SENTIMENT Source
    共用設定。
    """

    name: str = (
        "sentiment_source"
    )

    enabled: bool = True

    timeout_seconds: float = 10.0

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
                "Sentiment source "
                "name cannot be empty."
            )

        if (
            self.timeout_seconds
            <= 0
        ):

            raise ValueError(
                "timeout_seconds "
                "must be greater "
                "than 0."
            )


@dataclass(slots=True)
class SentimentSourceResult:
    """
    單一 SENTIMENT source
    抓取結果。

    payload:

        最終可以直接餵給：

            SentimentAgent

    errors:

        partial failure 不直接
        讓整個 source 崩潰。

    metadata:

        提供 service / dashboard /
        logging 使用。
    """

    source: str

    payload: SentimentInput = field(
        default_factory=(
            SentimentInput
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
        至少取得一類有效資料
        就視為 source 有成功。
        """

        return (
            self.has_payload_data(
                self.payload
            )
        )

    @staticmethod
    def has_payload_data(
        payload: SentimentInput,
    ) -> bool:

        return any(
            (
                bool(
                    payload.social_data
                ),

                bool(
                    payload
                    .funding_rate_data
                ),

                bool(
                    payload
                    .open_interest_data
                ),

                bool(
                    payload
                    .long_short_ratio_data
                ),

                bool(
                    payload
                    .liquidation_data
                ),

                bool(
                    payload
                    .market_activity_data
                ),

                bool(
                    payload.signals
                ),
            )
        )


class BaseSentimentSource(
    ABC
):
    """
    SENTIMENT 資料來源抽象基底。

    Source 的責任：

        External Data
            ↓
        Normalize raw structure
            ↓
        SentimentInput

    Source 不負責：

        - 判斷 LONG / SHORT
        - composite score
        - crowding calculation
        - trade decision

    上述工作由：

        SentimentAnalyzer
        SentimentAgent

    負責。
    """

    def __init__(
        self,
        config: SentimentSourceConfig,
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
    ) -> "BaseSentimentSource":

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
    ) -> SentimentSourceResult:
        """
        抓取並正規化 sentiment data。
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
                    f"Sentiment source "
                    f"'{self.name}' "
                    f"is disabled."
                )
            )

        if self.closed:

            raise RuntimeError(
                (
                    f"Sentiment source "
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

    @classmethod
    def extract_base_asset(
        cls,
        symbol: str,
    ) -> str:
        """
        BTC-USDT-SWAP
            ↓
        BTC
        """

        normalized = (
            cls.normalize_symbol(
                symbol
            )
        )

        base = (
            normalized
            .split("-")[0]
            .strip()
        )

        if not base:

            raise ValueError(
                (
                    f"Cannot resolve "
                    f"base asset from "
                    f"{symbol!r}."
                )
            )

        return base

    @classmethod
    def extract_instrument_family(
        cls,
        symbol: str,
    ) -> str:
        """
        BTC-USDT-SWAP
            ↓
        BTC-USDT

        BTC-USD-SWAP
            ↓
        BTC-USD
        """

        normalized = (
            cls.normalize_symbol(
                symbol
            )
        )

        parts = (
            normalized
            .split("-")
        )

        if (
            len(parts) >= 3
            and parts[-1]
            in (
                "SWAP",
                "FUTURES",
            )
        ):

            return "-".join(
                parts[:-1]
            )

        if len(parts) >= 2:

            return "-".join(
                parts[:2]
            )

        return normalized

    @staticmethod
    def safe_float(
        value: Any,
    ) -> float | None:

        if value is None:

            return None

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if (
            number
            != number
        ):

            return None

        if number in (
            float("inf"),
            float("-inf"),
        ):

            return None

        return number
