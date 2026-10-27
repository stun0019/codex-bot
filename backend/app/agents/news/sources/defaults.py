from __future__ import annotations

import os

from .manager import (
    NewsSourceManager,
)
from .rss import (
    RSSFeed,
    RSSNewsSource,
    RSSNewsSourceConfig,
)


def build_default_rss_feeds(
) -> list[RSSFeed]:
    """
    預設 crypto news RSS。

    這些 URL 全部只在 Python backend 使用。

    不需要 API Key。
    """

    feeds = [
        RSSFeed(
            name="CoinDesk",
            url=(
                "https://www.coindesk.com/"
                "arc/outboundfeeds/rss/"
            ),
        ),

        RSSFeed(
            name="Cointelegraph",
            url=(
                "https://cointelegraph.com/rss"
            ),
        ),

        RSSFeed(
            name="Decrypt",
            url=(
                "https://decrypt.co/feed"
            ),
        ),
    ]

    extra_feeds = (
        os.getenv(
            "CODEX_NEWS_EXTRA_RSS",
            "",
        )
        .strip()
    )

    if extra_feeds:

        for url in (
            extra_feeds.split(";")
        ):

            url = url.strip()

            if not url:

                continue

            feeds.append(
                RSSFeed(
                    url=url,
                )
            )

    return feeds


def build_default_rss_source(
) -> RSSNewsSource:

    config = RSSNewsSourceConfig(
        name="crypto_rss",

        feeds=(
            build_default_rss_feeds()
        ),

        default_limit=60,

        max_limit=200,

        timeout_seconds=12.0,

        max_concurrency=4,
    )

    return RSSNewsSource(
        config=config
    )


def build_default_news_source_manager(
) -> NewsSourceManager:
    """
    建立 NEWS 預設來源管理器。

    未來可以再加入：

    - SEC source
    - Exchange announcement source
    - Macro source
    - paid crypto API
    """

    return NewsSourceManager(
        sources=[
            build_default_rss_source()
        ]
    )
