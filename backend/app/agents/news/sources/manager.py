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

from ..models import NewsArticle
from .base import BaseNewsSource


@dataclass(slots=True)
class NewsSourceBatch:
    """
    多來源抓取結果。
    """

    articles: list[
        NewsArticle
    ] = field(
        default_factory=list
    )

    source_counts: dict[
        str,
        int,
    ] = field(
        default_factory=dict
    )

    errors: list[str] = field(
        default_factory=list
    )

    sources_requested: int = 0

    sources_succeeded: int = 0

    @property
    def article_count(
        self,
    ) -> int:

        return len(
            self.articles
        )


class NewsSourceManager:
    """
    統一管理多個 NEWS Source。

    功能：

    - Concurrent fetch
    - Source isolation
    - Partial failure
    - Cross-source dedupe
    - Time sorting
    - Global article limit
    """

    def __init__(
        self,
        sources: list[
            BaseNewsSource
        ] | None = None,
    ) -> None:

        self.sources = (
            list(
                sources or []
            )
        )

        self._closed = False

    async def __aenter__(
        self,
    ) -> "NewsSourceManager":

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:

        await self.close()

    def add(
        self,
        source: BaseNewsSource,
    ) -> None:

        if self._closed:

            raise RuntimeError(
                "NewsSourceManager "
                "is already closed."
            )

        self.sources.append(
            source
        )

    async def fetch(
        self,
        symbols: list[str] | None = None,
        limit_per_source: int = 50,
        total_limit: int = 200,
    ) -> NewsSourceBatch:

        if self._closed:

            raise RuntimeError(
                "NewsSourceManager "
                "is already closed."
            )

        if total_limit < 1:

            raise ValueError(
                "total_limit must "
                "be greater than 0."
            )

        if limit_per_source < 1:

            raise ValueError(
                "limit_per_source must "
                "be greater than 0."
            )

        normalized_symbols = (
            BaseNewsSource
            .normalize_symbols(
                symbols
            )
        )

        enabled_sources = [
            source
            for source
            in self.sources
            if source.enabled
        ]

        batch = NewsSourceBatch(
            sources_requested=len(
                enabled_sources
            )
        )

        if not enabled_sources:

            return batch

        async def run_source(
            source: BaseNewsSource,
        ) -> tuple[
            BaseNewsSource,
            list[NewsArticle] | None,
            Exception | None,
        ]:

            try:

                articles = (
                    await source.fetch(
                        symbols=(
                            normalized_symbols
                        ),
                        limit=(
                            limit_per_source
                        ),
                    )
                )

                return (
                    source,
                    articles,
                    None,
                )

            except Exception as exc:

                return (
                    source,
                    None,
                    exc,
                )

        results = await asyncio.gather(
            *[
                run_source(
                    source
                )
                for source
                in enabled_sources
            ]
        )

        combined: list[
            NewsArticle
        ] = []

        for (
            source,
            articles,
            error,
        ) in results:

            if error is not None:

                batch.errors.append(
                    (
                        f"{source.name}: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                )

                continue

            source_articles = (
                articles or []
            )

            batch.sources_succeeded += 1

            batch.source_counts[
                source.name
            ] = (
                batch.source_counts
                .get(
                    source.name,
                    0,
                )
                +
                len(
                    source_articles
                )
            )

            combined.extend(
                source_articles
            )

            internal_errors = getattr(
                source,
                "last_errors",
                [],
            )

            for internal_error in (
                internal_errors
            ):

                batch.errors.append(
                    (
                        f"{source.name}: "
                        f"{internal_error}"
                    )
                )

        combined = (
            BaseNewsSource
            .deduplicate_articles(
                combined
            )
        )

        combined.sort(
            key=self._sort_timestamp,
            reverse=True,
        )

        batch.articles = (
            combined[
                :total_limit
            ]
        )

        return batch

    async def close(
        self,
    ) -> None:

        if self._closed:

            return

        self._closed = True

        results = await asyncio.gather(
            *[
                source.close()
                for source
                in self.sources
                if not source.closed
            ],
            return_exceptions=True,
        )

        _ = results

    @staticmethod
    def _sort_timestamp(
        article: NewsArticle,
    ) -> float:

        value = (
            article.published_at
        )

        if value is None:

            return 0.0

        if value.tzinfo is None:

            value = value.replace(
                tzinfo=timezone.utc
            )

        return (
            value
            .astimezone(
                timezone.utc
            )
            .timestamp()
        )
