from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)
from dataclasses import dataclass
from typing import Any

from ..models import NewsArticle


@dataclass(slots=True)
class NewsSourceConfig:
    """
    新聞來源共用設定。

    name:
        Source 顯示名稱。

    default_limit:
        fetch() 未指定 limit 時，
        預設最多抓多少篇。

    max_limit:
        單次 fetch 最大文章數。

    timeout_seconds:
        HTTP 類型 source 可使用的
        request timeout。

    enabled:
        是否啟用此新聞來源。
    """

    name: str

    default_limit: int = 50

    max_limit: int = 200

    timeout_seconds: float = 10.0

    enabled: bool = True


class BaseNewsSource(ABC):
    """
    所有 NEWS Source 的共用介面。

    未來任何新聞來源都應繼承：

        BaseNewsSource

    並實作：

        async def fetch(...)

    不管來源是：

    - REST API
    - RSS
    - Exchange announcements
    - SEC / regulator feed
    - Macro feed
    - 自建 crawler
    - 第三方 crypto news API

    最終都必須輸出：

        list[NewsArticle]

    NEWS Agent 不需要知道資料來源細節。
    """

    def __init__(
        self,
        config: NewsSourceConfig,
    ) -> None:

        self.config = config

        self._closed = False

    @property
    def name(
        self,
    ) -> str:
        """
        Source 名稱。
        """

        return self.config.name

    @property
    def enabled(
        self,
    ) -> bool:
        """
        Source 是否啟用。
        """

        return self.config.enabled

    @property
    def closed(
        self,
    ) -> bool:
        """
        Source 是否已關閉。
        """

        return self._closed

    async def __aenter__(
        self,
    ) -> "BaseNewsSource":
        """
        支援：

            async with SomeNewsSource() as source:
                ...
        """

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
        symbols: list[str] | None = None,
        limit: int | None = None,
    ) -> list[NewsArticle]:
        """
        抓取新聞。

        symbols:
            想優先關注的市場。

            例如：

            [
                "BTC-USDT-SWAP",
                "ETH-USDT-SWAP",
            ]

            Source 可以：

            - 直接用 symbol 查詢
            - 只取 base asset
            - 忽略 symbols
            - 抓全市場新聞

            由各 Source 自行決定。

        limit:
            最多回傳幾篇新聞。

        回傳：

            list[NewsArticle]

        Source 必須盡量保證：

        - title 有值
        - source 有值
        - published_at 若有則提供
        - url 若有則提供
        - content 若有則提供
        - symbols 若能判斷則提供
        """

        raise NotImplementedError

    async def close(
        self,
    ) -> None:
        """
        關閉 Source。

        沒有 HTTP client 的 Source
        可以直接使用此預設實作。

        有 httpx.AsyncClient 等資源的
        Source 應 override 並在最後呼叫：

            await super().close()
        """

        self._closed = True

    def resolve_limit(
        self,
        limit: int | None,
    ) -> int:
        """
        統一處理文章數量限制。
        """

        if limit is None:

            resolved = (
                self.config.default_limit
            )

        else:

            resolved = int(limit)

        if resolved < 1:

            raise ValueError(
                "News source limit must be "
                "greater than 0."
            )

        return min(
            resolved,
            self.config.max_limit,
        )

    @staticmethod
    def normalize_symbols(
        symbols: list[str] | None,
    ) -> list[str]:
        """
        正規化交易對。

        輸入：

            [
                "btc-usdt-swap",
                " BTC-USDT-SWAP ",
                "ETH-USDT-SWAP",
            ]

        輸出：

            [
                "BTC-USDT-SWAP",
                "ETH-USDT-SWAP",
            ]
        """

        if not symbols:

            return []

        result: list[str] = []

        seen: set[str] = set()

        for symbol in symbols:

            if not symbol:

                continue

            normalized = (
                symbol
                .strip()
                .upper()
            )

            if not normalized:

                continue

            if normalized in seen:

                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return result

    @classmethod
    def extract_base_assets(
        cls,
        symbols: list[str] | None,
    ) -> list[str]:
        """
        從交易對取出 base asset。

        例如：

            BTC-USDT-SWAP
            ETH-USDT-SWAP
            SOL-USDT

        轉成：

            BTC
            ETH
            SOL
        """

        normalized_symbols = (
            cls.normalize_symbols(
                symbols
            )
        )

        result: list[str] = []

        seen: set[str] = set()

        for symbol in normalized_symbols:

            base = (
                symbol
                .split("-")[0]
                .strip()
            )

            if not base:

                continue

            if base in seen:

                continue

            seen.add(
                base
            )

            result.append(
                base
            )

        return result

    @staticmethod
    def deduplicate_articles(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Source 層的簡單去重。

        這不是 NewsAnalyzer 的完整事件去重。

        這裡只處理最明顯的：

        - 相同 URL
        - 相同 title

        真正的語意事件合併仍由：

            NewsAnalyzer

        負責。
        """

        result: list[
            NewsArticle
        ] = []

        seen_urls: set[str] = (
            set()
        )

        seen_titles: set[str] = (
            set()
        )

        for article in articles:

            url_key = ""

            if article.url:

                url_key = (
                    article.url
                    .strip()
                    .lower()
                )

            title_key = (
                article.title
                .strip()
                .lower()
            )

            if (
                url_key
                and url_key
                in seen_urls
            ):

                continue

            if (
                title_key
                and title_key
                in seen_titles
            ):

                continue

            if url_key:

                seen_urls.add(
                    url_key
                )

            if title_key:

                seen_titles.add(
                    title_key
                )

            result.append(
                article
            )

        return result

    def ensure_available(
        self,
    ) -> None:
        """
        在 fetch 前確認 Source 狀態。

        各 Source 可以在 fetch() 開頭：

            self.ensure_available()
        """

        if self._closed:

            raise RuntimeError(
                f"News source "
                f"{self.name!r} "
                f"is already closed."
            )

        if not self.enabled:

            raise RuntimeError(
                f"News source "
                f"{self.name!r} "
                f"is disabled."
            )
