from __future__ import annotations

import math
import re

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from difflib import SequenceMatcher

from ..models import TradeBias

from .models import (
    NewsArticle,
    NewsCategory,
    NewsEvent,
    NewsInput,
)


@dataclass(slots=True)
class NewsAnalyzerConfig:
    """
    NEWS deterministic analyzer 設定。

    這一層負責：

    - 新聞清洗
    - 去重
    - 分類
    - Symbol 關聯
    - 多來源事件合併
    - 初步 impact score
    - 初步 confidence

    不負責：

    - 最終語意判斷
    - LONG / SHORT 判斷
    - 交易決策

    方向性判斷之後交給 LLM。
    """

    duplicate_similarity_threshold: float = 0.82

    max_articles: int = 200

    max_age_hours: float = 72.0

    default_impact_score: float = 0.30


class NewsAnalyzer:
    """
    NEWS Agent 的 deterministic pre-analyzer。

    Pipeline:

        NewsArticle[]
            ↓
        normalize
            ↓
        filter stale articles
            ↓
        deduplicate / cluster
            ↓
        classify category
            ↓
        detect affected symbols
            ↓
        preliminary impact score
            ↓
        NewsEvent[]
    """

    _CATEGORY_KEYWORDS: dict[
        NewsCategory,
        tuple[str, ...],
    ] = {
        NewsCategory.MACRO: (
            "fed",
            "federal reserve",
            "interest rate",
            "rate cut",
            "rate hike",
            "inflation",
            "cpi",
            "ppi",
            "jobs report",
            "nonfarm",
            "non-farm",
            "unemployment",
            "gdp",
            "fomc",
            "powell",
            "treasury",
            "recession",
            "liquidity",
        ),

        NewsCategory.REGULATION: (
            "sec",
            "cftc",
            "regulation",
            "regulator",
            "regulatory",
            "lawsuit",
            "court",
            "legal",
            "ban",
            "approved",
            "approval",
            "license",
            "licensed",
            "compliance",
            "legislation",
            "bill",
        ),

        NewsCategory.EXCHANGE: (
            "exchange",
            "binance",
            "okx",
            "coinbase",
            "bybit",
            "kraken",
            "bitget",
            "bingx",
            "listing",
            "delisting",
            "withdrawal",
            "deposit",
            "maintenance",
        ),

        NewsCategory.SECURITY: (
            "hack",
            "hacked",
            "exploit",
            "exploited",
            "vulnerability",
            "attack",
            "breach",
            "stolen",
            "drained",
            "phishing",
            "security incident",
        ),

        NewsCategory.ETF: (
            "etf",
            "exchange traded fund",
            "exchange-traded fund",
            "spot bitcoin",
            "spot ethereum",
            "institutional inflow",
            "institutional outflow",
        ),

        NewsCategory.PROTOCOL: (
            "protocol",
            "mainnet",
            "testnet",
            "upgrade",
            "hard fork",
            "fork",
            "validator",
            "staking",
            "governance",
            "proposal",
            "defi",
            "bridge",
        ),

        NewsCategory.TOKEN: (
            "token",
            "airdrop",
            "unlock",
            "token unlock",
            "burn",
            "mint",
            "supply",
            "vesting",
            "launch",
        ),

        NewsCategory.MARKET: (
            "bitcoin",
            "ethereum",
            "crypto",
            "cryptocurrency",
            "market",
            "rally",
            "selloff",
            "liquidation",
            "liquidations",
            "all-time high",
            "ath",
            "price",
            "trading",
        ),
    }


    _CATEGORY_BASE_IMPACT: dict[
        NewsCategory,
        float,
    ] = {
        NewsCategory.SECURITY: 0.70,

        NewsCategory.REGULATION: 0.65,

        NewsCategory.ETF: 0.62,

        NewsCategory.MACRO: 0.60,

        NewsCategory.EXCHANGE: 0.52,

        NewsCategory.PROTOCOL: 0.48,

        NewsCategory.TOKEN: 0.45,

        NewsCategory.MARKET: 0.38,

        NewsCategory.OTHER: 0.30,
    }


    _SYMBOL_ALIASES: dict[
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
        config: NewsAnalyzerConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else NewsAnalyzerConfig()
        )


    def analyze(
        self,
        payload: NewsInput,
    ) -> list[NewsEvent]:
        """
        將 NewsInput 轉換成初步 NewsEvent。

        最終輸出的數量受：

            payload.max_events

        限制。
        """

        articles = self._prepare_articles(
            payload.articles
        )

        if not articles:
            return []

        clusters = self._cluster_articles(
            articles
        )

        events: list[NewsEvent] = []

        for cluster in clusters:

            event = self._build_event(
                articles=cluster,
                focus_symbols=payload.focus_symbols,
            )

            events.append(
                event
            )

        events.sort(
            key=lambda event: (
                event.impact_score,
                event.confidence,
                self._datetime_sort_value(
                    event.published_at
                ),
            ),
            reverse=True,
        )

        return events[
            :payload.max_events
        ]


    def _prepare_articles(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        清洗與排序新聞。

        - 限制文章數量
        - 過濾過舊文章
        - 最新文章優先
        """

        now = datetime.now(
            timezone.utc
        )

        prepared: list[
            NewsArticle
        ] = []

        for article in articles[
            :self.config.max_articles
        ]:

            if (
                article.published_at
                is not None
            ):

                published_at = (
                    self._ensure_utc(
                        article.published_at
                    )
                )

                age_hours = (
                    now
                    - published_at
                ).total_seconds() / 3600.0

                if (
                    age_hours
                    >
                    self.config.max_age_hours
                ):
                    continue

            prepared.append(
                article
            )

        prepared.sort(
            key=lambda article:
                self._datetime_sort_value(
                    article.published_at
                ),
            reverse=True,
        )

        return prepared


    def _cluster_articles(
        self,
        articles: list[NewsArticle],
    ) -> list[list[NewsArticle]]:
        """
        將相同事件的新聞合併成 cluster。

        判斷方式：

        1. 相同 URL
        2. 相似標題

        例如：

            Reuters:
            Bitcoin ETF inflows surge...

            Bloomberg:
            Bitcoin ETF sees strong inflows...

        可能會被視為同一事件。
        """

        clusters: list[
            list[NewsArticle]
        ] = []

        for article in articles:

            matched_cluster: (
                list[NewsArticle]
                | None
            ) = None

            for cluster in clusters:

                if self._is_same_event(
                    article,
                    cluster[0],
                ):

                    matched_cluster = (
                        cluster
                    )

                    break

            if matched_cluster is None:

                clusters.append(
                    [article]
                )

            else:

                matched_cluster.append(
                    article
                )

        return clusters


    def _is_same_event(
        self,
        first: NewsArticle,
        second: NewsArticle,
    ) -> bool:
        """
        判斷兩篇文章是否可能描述同一事件。
        """

        if (
            first.url
            and second.url
            and first.url.strip()
            == second.url.strip()
        ):
            return True

        first_title = (
            self._normalize_text(
                first.title
            )
        )

        second_title = (
            self._normalize_text(
                second.title
            )
        )

        if (
            not first_title
            or not second_title
        ):
            return False

        if (
            first_title
            ==
            second_title
        ):
            return True

        similarity = (
            SequenceMatcher(
                None,
                first_title,
                second_title,
            ).ratio()
        )

        return (
            similarity
            >=
            self.config
            .duplicate_similarity_threshold
        )


    def _build_event(
        self,
        articles: list[NewsArticle],
        focus_symbols: list[str],
    ) -> NewsEvent:
        """
        將一個 article cluster
        轉成 NewsEvent。
        """

        representative = (
            articles[0]
        )

        combined_text = " ".join(
            filter(
                None,
                [
                    article.title
                    for article
                    in articles
                ]
                +
                [
                    article.content
                    for article
                    in articles
                    if article.content
                ],
            )
        )

        category = self._detect_category(
            combined_text
        )

        affected_symbols = (
            self._detect_symbols(
                articles=articles,
                text=combined_text,
                focus_symbols=focus_symbols,
            )
        )

        source_names = (
            self._unique_strings(
                [
                    article.source
                    for article
                    in articles
                    if article.source
                ]
            )
        )

        source_urls = (
            self._unique_strings(
                [
                    article.url
                    for article
                    in articles
                    if article.url
                ]
            )
        )

        published_at = (
            self._latest_datetime(
                [
                    article.published_at
                    for article
                    in articles
                    if article.published_at
                    is not None
                ]
            )
        )

        impact_score = (
            self._calculate_impact_score(
                category=category,
                affected_symbols=(
                    affected_symbols
                ),
                source_count=len(
                    source_names
                ),
                published_at=published_at,
                focus_symbols=focus_symbols,
            )
        )

        confidence = (
            self._calculate_confidence(
                articles=articles,
                affected_symbols=(
                    affected_symbols
                ),
                source_count=len(
                    source_names
                ),
            )
        )

        return NewsEvent(
            title=representative.title,

            category=category,

            affected_symbols=(
                affected_symbols
            ),

            # Deterministic analyzer
            # 暫時不判斷方向。
            #
            # LONG / SHORT
            # 之後交給 LLM。
            bias=TradeBias.NEUTRAL,

            impact_score=impact_score,

            confidence=confidence,

            description=(
                self._build_description(
                    articles=articles,
                    category=category,
                    affected_symbols=(
                        affected_symbols
                    ),
                )
            ),

            source_names=source_names,

            source_urls=source_urls,

            published_at=published_at,

            metadata={
                "article_count":
                    len(articles),

                "pre_analyzed":
                    True,

                "requires_llm_analysis":
                    True,
            },
        )


    def _detect_category(
        self,
        text: str,
    ) -> NewsCategory:
        """
        使用關鍵字做初步分類。

        此結果只是 pre-classification，
        未來可由 LLM 修正。
        """

        normalized = (
            self._normalize_text(
                text
            )
        )

        best_category = (
            NewsCategory.OTHER
        )

        best_score = 0

        for (
            category,
            keywords,
        ) in (
            self._CATEGORY_KEYWORDS
            .items()
        ):

            score = 0

            for keyword in keywords:

                if self._contains_phrase(
                    normalized,
                    keyword,
                ):

                    score += 1

            if score > best_score:

                best_score = (
                    score
                )

                best_category = (
                    category
                )

        return best_category


    def _detect_symbols(
        self,
        articles: list[NewsArticle],
        text: str,
        focus_symbols: list[str],
    ) -> list[str]:
        """
        找出事件可能影響的交易標的。

        優先順序：

        1. Article 明確提供 symbols
        2. focus_symbols 關聯
        3. 常見 crypto alias
        """

        result: list[str] = []

        normalized_text = (
            self._normalize_text(
                text
            )
        )


        # 文章來源直接提供的 symbol

        for article in articles:

            for symbol in article.symbols:

                normalized_symbol = (
                    self._normalize_symbol(
                        symbol
                    )
                )

                if normalized_symbol:

                    result.append(
                        normalized_symbol
                    )


        # SCOUT 或上游傳入的 focus symbols

        for symbol in focus_symbols:

            normalized_symbol = (
                self._normalize_symbol(
                    symbol
                )
            )

            if not normalized_symbol:
                continue

            base = (
                normalized_symbol
                .split("-")[0]
            )

            aliases = (
                self._SYMBOL_ALIASES
                .get(
                    base,
                    (
                        base.lower(),
                    ),
                )
            )

            if any(
                self._contains_phrase(
                    normalized_text,
                    alias,
                )
                for alias
                in aliases
            ):

                result.append(
                    normalized_symbol
                )


        # 沒有 focus symbol 時，
        # 仍可識別常見 crypto。

        if not focus_symbols:

            for (
                base,
                aliases,
            ) in (
                self._SYMBOL_ALIASES
                .items()
            ):

                if any(
                    self._contains_phrase(
                        normalized_text,
                        alias,
                    )
                    for alias
                    in aliases
                ):

                    result.append(
                        f"{base}-USDT-SWAP"
                    )

        return (
            self._unique_strings(
                result
            )
        )


    def _calculate_impact_score(
        self,
        category: NewsCategory,
        affected_symbols: list[str],
        source_count: int,
        published_at: datetime | None,
        focus_symbols: list[str],
    ) -> float:
        """
        初步事件重要度評分。

        不是價格方向預測。

        主要考慮：

        - Category
        - 是否影響指定市場
        - 多來源確認
        - 新聞新鮮度
        """

        score = (
            self._CATEGORY_BASE_IMPACT
            .get(
                category,
                self.config
                .default_impact_score,
            )
        )


        # 有明確 affected symbol

        if affected_symbols:

            score += 0.08


        # 與 focus symbols 有交集

        if focus_symbols:

            normalized_focus = {
                self._normalize_symbol(
                    symbol
                )
                for symbol
                in focus_symbols
            }

            normalized_focus.discard(
                ""
            )

            if any(
                symbol
                in normalized_focus
                for symbol
                in affected_symbols
            ):

                score += 0.10


        # 多家來源確認

        if source_count >= 2:

            score += 0.05

        if source_count >= 3:

            score += 0.04


        # Recency

        recency_score = (
            self._calculate_recency_score(
                published_at
            )
        )

        score += (
            recency_score
            *
            0.08
        )

        return round(
            max(
                0.0,
                min(
                    1.0,
                    score,
                ),
            ),
            6,
        )


    def _calculate_confidence(
        self,
        articles: list[NewsArticle],
        affected_symbols: list[str],
        source_count: int,
    ) -> float:
        """
        初步資料品質 confidence。

        注意：

        這不是對市場方向的信心。

        它表示：

            NewsAnalyzer 對事件整理結果
            的資料完整程度。
        """

        if not articles:
            return 0.0

        score = 0.35


        if source_count >= 1:

            score += 0.10


        if source_count >= 2:

            score += 0.15


        if affected_symbols:

            score += 0.10


        if any(
            article.url
            for article
            in articles
        ):

            score += 0.08


        if any(
            article.content
            for article
            in articles
        ):

            score += 0.08


        if any(
            article.published_at
            is not None
            for article
            in articles
        ):

            score += 0.07


        return round(
            max(
                0.0,
                min(
                    1.0,
                    score,
                ),
            ),
            6,
        )


    def _calculate_recency_score(
        self,
        published_at: datetime | None,
    ) -> float:
        """
        新聞越新，score 越接近 1。

        使用指數衰減。

        約：

        0 小時 -> 1.0
        12 小時 -> ~0.61
        24 小時 -> ~0.37
        48 小時 -> ~0.14
        """

        if published_at is None:
            return 0.25

        now = datetime.now(
            timezone.utc
        )

        published_utc = (
            self._ensure_utc(
                published_at
            )
        )

        age_hours = max(
            0.0,
            (
                now
                - published_utc
            ).total_seconds()
            /
            3600.0,
        )

        return math.exp(
            -age_hours
            /
            24.0
        )


    def _build_description(
        self,
        articles: list[NewsArticle],
        category: NewsCategory,
        affected_symbols: list[str],
    ) -> str:
        """
        建立 deterministic event description。

        真正自然語言摘要之後可交由 LLM。
        """

        parts: list[str] = []

        parts.append(
            f"Category: {category.value}."
        )

        parts.append(
            f"Combined from {len(articles)} article"
            f"{'' if len(articles) == 1 else 's'}."
        )

        if affected_symbols:

            parts.append(
                "Affected markets: "
                +
                ", ".join(
                    affected_symbols
                )
                +
                "."
            )

        else:

            parts.append(
                "No specific market symbol "
                "was identified during "
                "pre-analysis."
            )

        return " ".join(
            parts
        )


    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        """
        Normalize text for matching.
        """

        value = (
            value
            .lower()
            .strip()
        )

        value = re.sub(
            r"https?://\S+",
            " ",
            value,
        )

        value = re.sub(
            r"[^a-z0-9\s\-]",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()


    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """
        將 symbol 統一成大寫格式。

        BTC-USDT-SWAP
        """

        if not symbol:
            return ""

        return (
            symbol
            .strip()
            .upper()
        )


    @staticmethod
    def _contains_phrase(
        text: str,
        phrase: str,
    ) -> bool:
        """
        安全判斷 keyword / phrase。

        單字使用 word boundary，
        多字詞使用 substring。
        """

        phrase = (
            phrase
            .lower()
            .strip()
        )

        if not phrase:
            return False

        if " " in phrase:

            return (
                phrase
                in text
            )

        pattern = (
            rf"\b{re.escape(phrase)}\b"
        )

        return (
            re.search(
                pattern,
                text,
            )
            is not None
        )


    @staticmethod
    def _unique_strings(
        values: list[str],
    ) -> list[str]:
        """
        保留原順序去重。
        """

        result: list[str] = []

        seen: set[str] = set()

        for value in values:

            if not value:
                continue

            normalized = (
                value.strip()
            )

            key = (
                normalized.lower()
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            result.append(
                normalized
            )

        return result


    @staticmethod
    def _ensure_utc(
        value: datetime,
    ) -> datetime:
        """
        確保 datetime 為 UTC-aware。
        """

        if value.tzinfo is None:

            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )


    @classmethod
    def _latest_datetime(
        cls,
        values: list[datetime],
    ) -> datetime | None:
        """
        取得最新時間。
        """

        if not values:
            return None

        normalized = [
            cls._ensure_utc(
                value
            )
            for value
            in values
        ]

        return max(
            normalized
        )


    @classmethod
    def _datetime_sort_value(
        cls,
        value: datetime | None,
    ) -> float:
        """
        datetime -> timestamp。

        None 排最後。
        """

        if value is None:
            return 0.0

        return (
            cls._ensure_utc(
                value
            )
            .timestamp()
        )
