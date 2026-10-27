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
    所有新聞來源共用設定。
    """

    name: str

    default_limit: int = 50

    max_limit: int = 200

    timeout_seconds: float = 10.0

    enabled: bool = True


class BaseNewsSource(ABC):
    """
    所有 NEWS Source 的抽象基底。

    所有來源最終都必須輸出：

        list[NewsArticle]
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

        return self.config.name

    @property
    def enabled(
        self,
    ) -> bool:

        return self.config.enabled

    @property
    def closed(
        self,
    ) -> bool:

        return self._closed

    async def __aenter__(
        self,
    ) -> "BaseNewsSource":

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

        raise NotImplementedError

    async def close(
        self,
    ) -> None:

        self._closed = True

    def resolve_limit(
        self,
        limit: int | None,
    ) -> int:

        if limit is None:

            resolved = (
                self.config.default_limit
            )

        else:

            resolved = int(
                limit
            )

        if resolved < 1:

            raise ValueError(
                "News source limit must "
                "be greater than 0."
            )

        return min(
            resolved,
            self.config.max_limit,
        )

    @staticmethod
    def normalize_symbols(
        symbols: list[str] | None,
    ) -> list[str]:

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
        Source 層的「明確重複」去重。

        去除：

        1. 完全相同 URL
        2. 同一來源 + 完全相同 title

        不會去除：

        CoinDesk:
            Bitcoin ETF approved

        Reuters:
            Bitcoin ETF approved

        因為 NewsAnalyzer 需要保留
        多來源確認能力。
        """

        result: list[
            NewsArticle
        ] = []

        seen_urls: set[str] = set()

        seen_source_titles: set[
            tuple[str, str]
        ] = set()

        for article in articles:

            url_key = ""

            if article.url:

                url_key = (
                    article.url
                    .strip()
                    .lower()
                )

            source_key = (
                article.source
                .strip()
                .lower()
            )

            title_key = (
                article.title
                .strip()
                .lower()
            )

            source_title_key = (
                source_key,
                title_key,
            )

            if (
                url_key
                and url_key in seen_urls
            ):

                continue

            if (
                title_key
                and source_title_key
                in seen_source_titles
            ):

                continue

            if url_key:

                seen_urls.add(
                    url_key
                )

            if title_key:

                seen_source_titles.add(
                    source_title_key
                )

            result.append(
                article
            )

        return result

    def ensure_available(
        self,
    ) -> None:

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
