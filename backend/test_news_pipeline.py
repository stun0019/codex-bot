from __future__ import annotations

import asyncio
import os

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.agents.models import (
    AgentStatus,
    MarketContext,
)

from app.agents.news import (
    BaseNewsSource,
    NewsAgent,
    NewsArticle,
    NewsService,
    NewsServiceConfig,
    NewsSourceConfig,
    NewsSourceManager,
    build_default_news_source_manager,
)


class FakeNewsSource(
    BaseNewsSource
):
    def __init__(
        self,
        name: str,
        articles: list[
            NewsArticle
        ],
        fail: bool = False,
    ) -> None:

        super().__init__(
            NewsSourceConfig(
                name=name,
            )
        )

        self.articles = articles

        self.fail = fail

    async def fetch(
        self,
        symbols=None,
        limit=None,
    ) -> list[NewsArticle]:

        self.ensure_available()

        if self.fail:

            raise RuntimeError(
                "Fake source failure."
            )

        resolved_limit = (
            self.resolve_limit(
                limit
            )
        )

        return self.articles[
            :resolved_limit
        ]


def build_context(
) -> MarketContext:

    return MarketContext(
        symbol=(
            "BTC-USDT-SWAP"
        ),

        exchange="OKX",

        market_type="swap",

        timeframes=[
            "15m",
            "1H",
            "4H",
        ],

        metadata={
            "test":
                True,

            "source":
                "test_news_pipeline.py",
        },
    )


def build_articles(
) -> tuple[
    list[NewsArticle],
    list[NewsArticle],
]:

    now = datetime.now(
        timezone.utc
    )

    source_a = [
        NewsArticle(
            title=(
                "Bitcoin ETF demand "
                "increases"
            ),

            source="Source A",

            published_at=(
                now
                -
                timedelta(
                    minutes=5
                )
            ),

            url=(
                "https://example.com/a"
            ),

            content=(
                "Bitcoin ETF institutional "
                "demand increased."
            ),

            symbols=[
                "BTC"
            ],
        )
    ]

    source_b = [
        NewsArticle(
            title=(
                "Bitcoin ETF demand "
                "increases"
            ),

            source="Source B",

            published_at=(
                now
                -
                timedelta(
                    minutes=4
                )
            ),

            url=(
                "https://example.com/b"
            ),

            content=(
                "A second independent "
                "source confirms increasing "
                "Bitcoin ETF demand."
            ),

            symbols=[
                "BTC-USDT-SWAP"
            ],
        )
    ]

    return (
        source_a,
        source_b,
    )


async def test_manager(
) -> bool:

    print(
        "\nTEST 1 - SOURCE MANAGER"
    )

    a,
    b = build_articles()

    manager = NewsSourceManager(
        sources=[
            FakeNewsSource(
                "source_a",
                a,
            ),

            FakeNewsSource(
                "source_b",
                b,
            ),

            FakeNewsSource(
                "broken",
                [],
                fail=True,
            ),
        ]
    )

    try:

        batch = (
            await manager.fetch(
                symbols=[
                    "BTC-USDT-SWAP"
                ],

                limit_per_source=10,

                total_limit=20,
            )
        )

        print(
            f"Articles: "
            f"{batch.article_count}"
        )

        print(
            f"Sources succeeded: "
            f"{batch.sources_succeeded}/"
            f"{batch.sources_requested}"
        )

        print(
            f"Errors: "
            f"{len(batch.errors)}"
        )

        if (
            batch.article_count
            != 2
        ):

            print(
                "FAIL: cross-source "
                "confirmation was lost."
            )

            return False

        if (
            batch.sources_succeeded
            != 2
        ):

            return False

        if not batch.errors:

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await manager.close()


async def test_service(
) -> bool:

    print(
        "\nTEST 2 - NEWS SERVICE"
    )

    a,
    b = build_articles()

    manager = NewsSourceManager(
        sources=[
            FakeNewsSource(
                "source_a",
                a,
            ),

            FakeNewsSource(
                "source_b",
                b,
            ),
        ]
    )

    service = NewsService(
        agent=NewsAgent(
            enable_llm=False
        ),

        source_manager=manager,

        config=NewsServiceConfig(
            cache_ttl_seconds=120,
        ),
    )

    try:

        context = (
            build_context()
        )

        output = (
            await service.analyze(
                context=context
            )
        )

        print(
            f"Status: "
            f"{output.status.value}"
        )

        print(
            f"Events: "
            f"{len(output.events)}"
        )

        print(
            f"Source Articles: "
            f"{output.data.get('source_articles')}"
        )

        if (
            output.status
            !=
            AgentStatus.SUCCESS
        ):

            return False

        if not output.events:

            return False

        if (
            output.data.get(
                "sources_succeeded"
            )
            != 2
        ):

            return False

        if (
            output.data.get(
                "news_cache_hit"
            )
            is not False
        ):

            return False

        second = (
            await service.analyze(
                context=context
            )
        )

        if (
            second.data.get(
                "news_cache_hit"
            )
            is not True
        ):

            print(
                "FAIL: cache was "
                "not used."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await service.close()


async def test_live_rss(
) -> bool:

    print(
        "\nTEST 3 - LIVE RSS"
    )

    if (
        os.getenv(
            "RUN_LIVE_NEWS_RSS",
            "",
        ).strip()
        != "1"
    ):

        print(
            "SKIPPED"
        )

        print(
            "Set "
            "RUN_LIVE_NEWS_RSS=1 "
            "to enable."
        )

        return True

    manager = (
        build_default_news_source_manager()
    )

    try:

        batch = (
            await manager.fetch(
                symbols=[
                    "BTC-USDT-SWAP",
                    "ETH-USDT-SWAP",
                ],

                limit_per_source=20,

                total_limit=30,
            )
        )

        print(
            f"Articles: "
            f"{batch.article_count}"
        )

        print(
            f"Sources: "
            f"{batch.sources_succeeded}/"
            f"{batch.sources_requested}"
        )

        for error in batch.errors:

            print(
                f"ERROR: {error}"
            )

        for article in (
            batch.articles[:10]
        ):

            print(
                f"- [{article.source}] "
                f"{article.title}"
            )

        if not batch.articles:

            print(
                "FAIL: No live "
                "RSS articles."
            )

            return False

        print(
            "RESULT: PASS"
        )

        return True

    finally:

        await manager.close()


async def main(
) -> int:

    results = [
        await test_manager(),
        await test_service(),
        await test_live_rss(),
    ]

    passed = sum(
        1
        for result
        in results
        if result
    )

    print(
        "\n"
        "=============================="
    )

    print(
        f"NEWS PIPELINE: "
        f"{passed}/{len(results)}"
    )

    print(
        "=============================="
    )

    return (
        0
        if all(results)
        else 1
    )


if __name__ == "__main__":

    try:

        raise SystemExit(
            asyncio.run(
                main()
            )
        )

    except KeyboardInterrupt:

        raise SystemExit(
            130
        )
