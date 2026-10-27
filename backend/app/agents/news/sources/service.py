from __future__ import annotations

import hashlib
import time

from dataclasses import (
    dataclass,
)

from ..models import (
    MarketContext,
)

from .agent import (
    NewsAgent,
)
from .models import (
    NewsArticle,
    NewsInput,
    NewsOutput,
)
from .sources.base import (
    BaseNewsSource,
)
from .sources.defaults import (
    build_default_news_source_manager,
)
from .sources.manager import (
    NewsSourceManager,
)


@dataclass(slots=True)
class NewsServiceConfig:
    """
    NEWS orchestration 設定。
    """

    limit_per_source: int = 60

    total_article_limit: int = 150

    max_events: int = 10

    include_context_symbol: bool = True

    cache_ttl_seconds: float = 120.0

    cache_max_entries: int = 32


@dataclass(slots=True)
class _CacheEntry:
    created_at: float

    output: NewsOutput


class NewsService:
    """
    真實 NEWS pipeline orchestration。

    Pipeline:

        Sources
            ↓
        NewsSourceManager
            ↓
        NewsArticle[]
            ↓
        NewsInput
            ↓
        NewsAgent
            ↓
        NewsOutput

    同時負責：

    - Source metadata
    - Partial source failures
    - Article limits
    - Focus symbols
    - LLM duplicate-call cache
    """

    def __init__(
        self,
        agent: NewsAgent | None = None,
        source_manager: (
            NewsSourceManager
            | None
        ) = None,
        config: (
            NewsServiceConfig
            | None
        ) = None,
    ) -> None:

        self.agent = (
            agent
            if agent is not None
            else NewsAgent()
        )

        self.source_manager = (
            source_manager
            if source_manager is not None
            else (
                build_default_news_source_manager()
            )
        )

        self.config = (
            config
            if config is not None
            else NewsServiceConfig()
        )

        self._cache: dict[
            str,
            _CacheEntry,
        ] = {}

        self._closed = False

    async def __aenter__(
        self,
    ) -> "NewsService":

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:

        await self.close()

    async def analyze(
        self,
        context: MarketContext,
        focus_symbols: (
            list[str]
            | None
        ) = None,
    ) -> NewsOutput:

        if self._closed:

            raise RuntimeError(
                "NewsService "
                "is already closed."
            )

        symbols = (
            self._resolve_symbols(
                context=context,
                focus_symbols=(
                    focus_symbols
                ),
            )
        )

        source_batch = (
            await self.source_manager.fetch(
                symbols=symbols,

                limit_per_source=(
                    self.config
                    .limit_per_source
                ),

                total_limit=(
                    self.config
                    .total_article_limit
                ),
            )
        )

        payload = NewsInput(
            articles=(
                source_batch.articles
            ),

            focus_symbols=symbols,

            max_events=(
                self.config.max_events
            ),
        )

        cache_key = (
            self._build_cache_key(
                symbols=symbols,
                articles=(
                    source_batch.articles
                ),
            )
        )

        cached = (
            self._get_cached(
                cache_key
            )
        )

        if cached is not None:

            return (
                self._attach_source_data(
                    output=cached,
                    source_batch=(
                        source_batch
                    ),
                    cache_hit=True,
                )
            )

        output = (
            await self.agent.analyze(
                context=context,
                payload=payload,
            )
        )

        output = (
            self._attach_source_data(
                output=output,
                source_batch=(
                    source_batch
                ),
                cache_hit=False,
            )
        )

        self._store_cache(
            cache_key,
            output,
        )

        return output

    async def close(
        self,
    ) -> None:

        if self._closed:

            return

        self._closed = True

        await self.source_manager.close()

    def clear_cache(
        self,
    ) -> None:

        self._cache.clear()

    def _resolve_symbols(
        self,
        context: MarketContext,
        focus_symbols: (
            list[str]
            | None
        ),
    ) -> list[str]:

        symbols = (
            BaseNewsSource
            .normalize_symbols(
                focus_symbols
            )
        )

        if (
            self.config
            .include_context_symbol
            and context.symbol
            and context.symbol.upper()
            != "MARKET"
        ):

            context_symbol = (
                context.symbol
                .strip()
                .upper()
            )

            if (
                context_symbol
                and context_symbol
                not in symbols
            ):

                symbols.insert(
                    0,
                    context_symbol
                )

        return symbols

    def _attach_source_data(
        self,
        output: NewsOutput,
        source_batch,
        cache_hit: bool,
    ) -> NewsOutput:

        data = dict(
            output.data
        )

        data.update(
            {
                "source_articles":
                    source_batch
                    .article_count,

                "sources_requested":
                    source_batch
                    .sources_requested,

                "sources_succeeded":
                    source_batch
                    .sources_succeeded,

                "source_counts":
                    source_batch
                    .source_counts,

                "source_errors":
                    source_batch
                    .errors,

                "news_cache_hit":
                    cache_hit,
            }
        )

        return output.model_copy(
            update={
                "data": data
            },
            deep=True,
        )

    def _build_cache_key(
        self,
        symbols: list[str],
        articles: list[
            NewsArticle
        ],
    ) -> str:

        parts = [
            ",".join(
                sorted(
                    symbols
                )
            )
        ]

        for article in articles:

            parts.append(
                "|".join(
                    [
                        article.source,
                        article.title,
                        article.url or "",
                        (
                            article
                            .published_at
                            .isoformat()
                            if (
                                article
                                .published_at
                                is not None
                            )
                            else ""
                        ),
                    ]
                )
            )

        raw = "\n".join(
            parts
        )

        return hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()

    def _get_cached(
        self,
        key: str,
    ) -> NewsOutput | None:

        if (
            self.config
            .cache_ttl_seconds
            <= 0
        ):

            return None

        entry = (
            self._cache.get(
                key
            )
        )

        if entry is None:

            return None

        age = (
            time.monotonic()
            -
            entry.created_at
        )

        if (
            age
            >
            self.config
            .cache_ttl_seconds
        ):

            self._cache.pop(
                key,
                None,
            )

            return None

        return (
            entry.output
            .model_copy(
                deep=True
            )
        )

    def _store_cache(
        self,
        key: str,
        output: NewsOutput,
    ) -> None:

        if (
            self.config
            .cache_ttl_seconds
            <= 0
        ):

            return

        self._cache[
            key
        ] = _CacheEntry(
            created_at=(
                time.monotonic()
            ),

            output=(
                output.model_copy(
                    deep=True
                )
            ),
        )

        while (
            len(
                self._cache
            )
            >
            self.config
            .cache_max_entries
        ):

            oldest_key = min(
                self._cache,
                key=lambda cache_key:
                    self._cache[
                        cache_key
                    ].created_at,
            )

            self._cache.pop(
                oldest_key,
                None,
            )
