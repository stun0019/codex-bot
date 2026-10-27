from __future__ import annotations

import asyncio
import html
import re
import xml.etree.ElementTree as ET

from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from ..models import NewsArticle
from .base import (
    BaseNewsSource,
    NewsSourceConfig,
)


@dataclass(slots=True)
class RSSFeed:
    """
    單一 RSS / Atom Feed 設定。

    url:
        Feed URL。

    name:
        自訂來源名稱。

        若不指定，會優先使用：
        1. Feed 內的 title
        2. URL hostname

    symbols:
        此 Feed 若專門對應某些市場，
        可以預先指定。

        例如：

            [
                "BTC-USDT-SWAP",
                "ETH-USDT-SWAP",
            ]

        若留空則由文章文字做簡單推斷。

    enabled:
        是否啟用此 Feed。
    """

    url: str

    name: str | None = None

    symbols: list[str] = field(
        default_factory=list
    )

    enabled: bool = True


@dataclass(slots=True)
class RSSNewsSourceConfig(
    NewsSourceConfig
):
    """
    RSS News Source 設定。
    """

    name: str = "rss"

    feeds: list[RSSFeed] = field(
        default_factory=list
    )

    default_limit: int = 50

    max_limit: int = 200

    timeout_seconds: float = 10.0

    enabled: bool = True

    max_concurrency: int = 5

    user_agent: str = (
        "codex-bot-news/1.0"
    )


class RSSNewsSource(
    BaseNewsSource
):
    """
    Generic RSS / Atom 新聞來源。

    支援：

    - RSS 2.0
    - Atom
    - 多 Feed
    - async HTTP
    - Feed concurrency
    - 單一 Feed 失敗不中斷其他 Feed
    - title / URL 去重
    - published_at 解析
    - 基本 symbol detection

    最終統一輸出：

        list[NewsArticle]
    """

    _ASSET_ALIASES: dict[
        str,
        tuple[str, ...],
    ] = {
        "BTC": (
            "btc",
            "bitcoin",
        ),

        "ETH": (
            "eth",
            "ethereum",
            "ether",
        ),

        "SOL": (
            "sol",
            "solana",
        ),

        "XRP": (
            "xrp",
            "ripple",
        ),

        "DOGE": (
            "doge",
            "dogecoin",
        ),

        "ADA": (
            "ada",
            "cardano",
        ),

        "AVAX": (
            "avax",
            "avalanche",
        ),

        "LINK": (
            "link",
            "chainlink",
        ),

        "DOT": (
            "dot",
            "polkadot",
        ),

        "LTC": (
            "ltc",
            "litecoin",
        ),

        "BCH": (
            "bch",
            "bitcoin cash",
        ),

        "TRX": (
            "trx",
            "tron",
        ),

        "TON": (
            "ton",
            "toncoin",
        ),

        "SUI": (
            "sui",
        ),

        "APT": (
            "apt",
            "aptos",
        ),

        "ARB": (
            "arb",
            "arbitrum",
        ),

        "OP": (
            "op",
            "optimism",
        ),

        "NEAR": (
            "near",
            "near protocol",
        ),

        "ATOM": (
            "atom",
            "cosmos",
        ),
    }

    def __init__(
        self,
        config: RSSNewsSourceConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:

        super().__init__(
            config=config
        )

        self.config: (
            RSSNewsSourceConfig
        ) = config

        self._owns_client = (
            client is None
        )

        self.client = (
            client
            if client is not None
            else httpx.AsyncClient(
                timeout=httpx.Timeout(
                    self.config
                    .timeout_seconds
                ),
                follow_redirects=True,
                headers={
                    "User-Agent":
                        self.config
                        .user_agent,
                },
            )
        )

        self._last_errors: list[str] = []

    @property
    def last_errors(
        self,
    ) -> list[str]:
        """
        最近一次 fetch 的 Feed errors。

        回傳 copy，避免外部修改內部狀態。
        """

        return (
            self._last_errors.copy()
        )

    async def fetch(
        self,
        symbols: list[str] | None = None,
        limit: int | None = None,
    ) -> list[NewsArticle]:
        """
        抓取所有已啟用 RSS Feed。

        單一 Feed 發生錯誤時：

        - 記錄至 last_errors
        - 不讓其他 Feed 一起失敗
        """

        self.ensure_available()

        resolved_limit = (
            self.resolve_limit(
                limit
            )
        )

        normalized_symbols = (
            self.normalize_symbols(
                symbols
            )
        )

        feeds = [
            feed
            for feed
            in self.config.feeds
            if (
                feed.enabled
                and feed.url.strip()
            )
        ]

        if not feeds:

            return []

        self._last_errors = []

        semaphore = asyncio.Semaphore(
            max(
                1,
                self.config
                .max_concurrency,
            )
        )

        async def fetch_one(
            feed: RSSFeed,
        ) -> list[NewsArticle]:

            async with semaphore:

                try:

                    return (
                        await self._fetch_feed(
                            feed=feed,
                            focus_symbols=(
                                normalized_symbols
                            ),
                        )
                    )

                except Exception as exc:

                    self._last_errors.append(
                        (
                            f"{feed.url}: "
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        )
                    )

                    return []

        results = await asyncio.gather(
            *[
                fetch_one(
                    feed
                )
                for feed
                in feeds
            ]
        )

        articles: list[
            NewsArticle
        ] = []

        for feed_articles in results:

            articles.extend(
                feed_articles
            )

        articles = (
            self.deduplicate_articles(
                articles
            )
        )

        articles.sort(
            key=lambda article:
                self._datetime_sort_value(
                    article.published_at
                ),
            reverse=True,
        )

        return articles[
            :resolved_limit
        ]

    async def _fetch_feed(
        self,
        feed: RSSFeed,
        focus_symbols: list[str],
    ) -> list[NewsArticle]:
        """
        抓取單一 Feed。
        """

        response = (
            await self.client.get(
                feed.url
            )
        )

        response.raise_for_status()

        content = (
            response.content
        )

        if not content:

            return []

        try:

            root = (
                ET.fromstring(
                    content
                )
            )

        except ET.ParseError as exc:

            raise ValueError(
                "Invalid RSS/Atom XML."
            ) from exc

        root_name = (
            self._local_name(
                root.tag
            )
            .lower()
        )

        if root_name == "rss":

            return (
                self._parse_rss(
                    root=root,
                    feed=feed,
                    focus_symbols=(
                        focus_symbols
                    ),
                )
            )

        if root_name == "feed":

            return (
                self._parse_atom(
                    root=root,
                    feed=feed,
                    focus_symbols=(
                        focus_symbols
                    ),
                )
            )

        # 有些 RSS XML 的 root
        # 不一定直接是 <rss>。
        if self._find_first(
            root,
            "channel",
        ) is not None:

            return (
                self._parse_rss(
                    root=root,
                    feed=feed,
                    focus_symbols=(
                        focus_symbols
                    ),
                )
            )

        raise ValueError(
            "Unsupported RSS/Atom format."
        )

    def _parse_rss(
        self,
        root: ET.Element,
        feed: RSSFeed,
        focus_symbols: list[str],
    ) -> list[NewsArticle]:
        """
        Parse RSS 2.0。
        """

        channel = (
            self._find_first(
                root,
                "channel",
            )
        )

        if channel is None:

            return []

        feed_title = (
            self._child_text(
                channel,
                "title",
            )
        )

        source_name = (
            self._resolve_source_name(
                feed=feed,
                feed_title=feed_title,
            )
        )

        articles: list[
            NewsArticle
        ] = []

        for item in self._children(
            channel,
            "item",
        ):

            title = (
                self._child_text(
                    item,
                    "title",
                )
            )

            if not title:

                continue

            url = (
                self._child_text(
                    item,
                    "link",
                )
            )

            description = (
                self._child_text(
                    item,
                    "description",
                )
            )

            content_encoded = (
                self._child_text(
                    item,
                    "encoded",
                )
            )

            content = (
                content_encoded
                or description
                or ""
            )

            content = (
                self._clean_html(
                    content
                )
            )

            published_raw = (
                self._child_text(
                    item,
                    "pubDate",
                )
                or
                self._child_text(
                    item,
                    "published",
                )
                or
                self._child_text(
                    item,
                    "date",
                )
            )

            published_at = (
                self._parse_datetime(
                    published_raw
                )
            )

            article_symbols = (
                self._resolve_symbols(
                    feed=feed,
                    focus_symbols=(
                        focus_symbols
                    ),
                    title=title,
                    content=content,
                )
            )

            articles.append(
                NewsArticle(
                    title=title,

                    source=source_name,

                    published_at=(
                        published_at
                    ),

                    url=(
                        url
                        or None
                    ),

                    content=(
                        content
                        or None
                    ),

                    symbols=(
                        article_symbols
                    ),

                    metadata={
                        "source_type":
                            "rss",

                        "feed_url":
                            feed.url,

                        "feed_title":
                            feed_title,

                        "format":
                            "rss",
                    },
                )
            )

        return articles

    def _parse_atom(
        self,
        root: ET.Element,
        feed: RSSFeed,
        focus_symbols: list[str],
    ) -> list[NewsArticle]:
        """
        Parse Atom Feed。
        """

        feed_title = (
            self._child_text(
                root,
                "title",
            )
        )

        source_name = (
            self._resolve_source_name(
                feed=feed,
                feed_title=feed_title,
            )
        )

        articles: list[
            NewsArticle
        ] = []

        for entry in self._children(
            root,
            "entry",
        ):

            title = (
                self._child_text(
                    entry,
                    "title",
                )
            )

            if not title:

                continue

            url = (
                self._atom_link(
                    entry
                )
            )

            content = (
                self._child_text(
                    entry,
                    "content",
                )
                or
                self._child_text(
                    entry,
                    "summary",
                )
                or ""
            )

            content = (
                self._clean_html(
                    content
                )
            )

            published_raw = (
                self._child_text(
                    entry,
                    "published",
                )
                or
                self._child_text(
                    entry,
                    "updated",
                )
            )

            published_at = (
                self._parse_datetime(
                    published_raw
                )
            )

            article_symbols = (
                self._resolve_symbols(
                    feed=feed,
                    focus_symbols=(
                        focus_symbols
                    ),
                    title=title,
                    content=content,
                )
            )

            articles.append(
                NewsArticle(
                    title=title,

                    source=source_name,

                    published_at=(
                        published_at
                    ),

                    url=(
                        url
                        or None
                    ),

                    content=(
                        content
                        or None
                    ),

                    symbols=(
                        article_symbols
                    ),

                    metadata={
                        "source_type":
                            "rss",

                        "feed_url":
                            feed.url,

                        "feed_title":
                            feed_title,

                        "format":
                            "atom",
                    },
                )
            )

        return articles

    def _resolve_symbols(
        self,
        feed: RSSFeed,
        focus_symbols: list[str],
        title: str,
        content: str,
    ) -> list[str]:
        """
        判斷文章可能關聯的 Symbol。

        優先順序：

        1. RSSFeed 預先指定 symbols
        2. focus_symbols + 文章文字
        3. 常見 crypto alias

        這只是 Source 層初步標記。

        真正事件關聯仍由
        NewsAnalyzer / LLM 處理。
        """

        if feed.symbols:

            return (
                self.normalize_symbols(
                    feed.symbols
                )
            )

        combined_text = (
            f"{title} {content}"
            .lower()
        )

        detected: list[str] = []

        if focus_symbols:

            for symbol in (
                focus_symbols
            ):

                base = (
                    symbol
                    .split("-")[0]
                    .upper()
                )

                aliases = (
                    self._ASSET_ALIASES
                    .get(
                        base,
                        (
                            base.lower(),
                        ),
                    )
                )

                if any(
                    self._contains_term(
                        combined_text,
                        alias,
                    )
                    for alias
                    in aliases
                ):

                    detected.append(
                        symbol
                    )

        else:

            for (
                base,
                aliases,
            ) in (
                self._ASSET_ALIASES
                .items()
            ):

                if any(
                    self._contains_term(
                        combined_text,
                        alias,
                    )
                    for alias
                    in aliases
                ):

                    detected.append(
                        (
                            f"{base}"
                            "-USDT-SWAP"
                        )
                    )

        return (
            self.normalize_symbols(
                detected
            )
        )

    @staticmethod
    def _contains_term(
        text: str,
        term: str,
    ) -> bool:
        """
        避免例如：

            SOL

        誤匹配成：

            solution
        """

        term = (
            term
            .strip()
            .lower()
        )

        if not term:

            return False

        if " " in term:

            return (
                term in text
            )

        pattern = (
            rf"\b"
            rf"{re.escape(term)}"
            rf"\b"
        )

        return (
            re.search(
                pattern,
                text,
            )
            is not None
        )

    @staticmethod
    def _resolve_source_name(
        feed: RSSFeed,
        feed_title: str,
    ) -> str:
        """
        Source 名稱優先順序：

        1. RSSFeed.name
        2. Feed title
        3. hostname
        4. "RSS"
        """

        if (
            feed.name
            and feed.name.strip()
        ):

            return (
                feed.name.strip()
            )

        if feed_title:

            return (
                feed_title.strip()
            )

        parsed = (
            urlparse(
                feed.url
            )
        )

        if parsed.hostname:

            return (
                parsed.hostname
            )

        return "RSS"

    @staticmethod
    def _parse_datetime(
        value: str | None,
    ) -> datetime | None:
        """
        支援常見：

        RSS:
            Tue, 27 Oct 2026 08:00:00 GMT

        Atom:
            2026-10-27T08:00:00Z
        """

        if not value:

            return None

        value = (
            value.strip()
        )

        if not value:

            return None

        # RSS / RFC 2822

        try:

            parsed = (
                parsedate_to_datetime(
                    value
                )
            )

            if parsed is not None:

                if parsed.tzinfo is None:

                    parsed = (
                        parsed.replace(
                            tzinfo=(
                                timezone.utc
                            )
                        )
                    )

                return (
                    parsed.astimezone(
                        timezone.utc
                    )
                )

        except (
            TypeError,
            ValueError,
        ):

            pass

        # ISO 8601 / Atom

        try:

            iso_value = value

            if (
                iso_value.endswith(
                    "Z"
                )
            ):

                iso_value = (
                    iso_value[:-1]
                    +
                    "+00:00"
                )

            parsed = (
                datetime.fromisoformat(
                    iso_value
                )
            )

            if parsed.tzinfo is None:

                parsed = (
                    parsed.replace(
                        tzinfo=(
                            timezone.utc
                        )
                    )
                )

            return (
                parsed.astimezone(
                    timezone.utc
                )
            )

        except ValueError:

            return None

    @staticmethod
    def _clean_html(
        value: str,
    ) -> str:
        """
        RSS description/content 常包含 HTML。

        這裡做基本清理，
        避免把大量 HTML tag
        傳給 NewsAnalyzer / LLM。
        """

        if not value:

            return ""

        value = (
            html.unescape(
                value
            )
        )

        value = re.sub(
            r"<script\b[^>]*>.*?</script>",
            " ",
            value,
            flags=(
                re.IGNORECASE
                |
                re.DOTALL
            ),
        )

        value = re.sub(
            r"<style\b[^>]*>.*?</style>",
            " ",
            value,
            flags=(
                re.IGNORECASE
                |
                re.DOTALL
            ),
        )

        value = re.sub(
            r"<[^>]+>",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    @classmethod
    def _child_text(
        cls,
        element: ET.Element,
        name: str,
    ) -> str:
        """
        Namespace-independent child text。
        """

        for child in element:

            if (
                cls._local_name(
                    child.tag
                ).lower()
                ==
                name.lower()
            ):

                text = (
                    "".join(
                        child
                        .itertext()
                    )
                    .strip()
                )

                if text:

                    return text

        return ""

    @classmethod
    def _children(
        cls,
        element: ET.Element,
        name: str,
    ) -> list[ET.Element]:
        """
        找指定名稱的直接 children。
        """

        return [
            child

            for child
            in element

            if (
                cls._local_name(
                    child.tag
                ).lower()
                ==
                name.lower()
            )
        ]

    @classmethod
    def _find_first(
        cls,
        element: ET.Element,
        name: str,
    ) -> ET.Element | None:
        """
        Namespace-independent recursive search。
        """

        for child in element.iter():

            if (
                cls._local_name(
                    child.tag
                ).lower()
                ==
                name.lower()
            ):

                return child

        return None

    @classmethod
    def _atom_link(
        cls,
        entry: ET.Element,
    ) -> str:
        """
        Atom link 通常：

            <link href="..." />

        優先：

            rel="alternate"

        沒有則取第一個 href。
        """

        fallback = ""

        for child in entry:

            if (
                cls._local_name(
                    child.tag
                ).lower()
                !=
                "link"
            ):

                continue

            href = (
                child.attrib.get(
                    "href",
                    "",
                )
                .strip()
            )

            if not href:

                text = (
                    child.text
                    or ""
                ).strip()

                if text:

                    href = text

            if not href:

                continue

            if not fallback:

                fallback = href

            rel = (
                child.attrib.get(
                    "rel",
                    "alternate",
                )
                .strip()
                .lower()
            )

            if rel == "alternate":

                return href

        return fallback

    @staticmethod
    def _local_name(
        tag: str,
    ) -> str:
        """
        去掉 XML namespace。

        例如：

            {http://www.w3.org/2005/Atom}entry

        轉成：

            entry
        """

        if "}" in tag:

            return (
                tag
                .split(
                    "}",
                    1,
                )[1]
            )

        if ":" in tag:

            return (
                tag
                .split(
                    ":",
                    1,
                )[1]
            )

        return tag

    @staticmethod
    def _datetime_sort_value(
        value: datetime | None,
    ) -> float:
        """
        最新新聞排前面。

        沒有時間的文章排後面。
        """

        if value is None:

            return 0.0

        if value.tzinfo is None:

            value = (
                value.replace(
                    tzinfo=(
                        timezone.utc
                    )
                )
            )

        return (
            value
            .astimezone(
                timezone.utc
            )
            .timestamp()
        )

    async def close(
        self,
    ) -> None:
        """
        關閉 HTTP client。
        """

        if (
            self._owns_client
            and not self.client.is_closed
        ):

            await self.client.aclose()

        await super().close()
