from __future__ import annotations

import asyncio
from typing import Any

from app.agents.models import (
    AgentStatus,
    MarketContext,
)
from app.agents.scout import (
    ScoutAgent,
    ScoutInput,
)


def format_number(
    value: Any,
    decimals: int = 4,
) -> str:
    """
    將數字格式化為較容易閱讀的格式。
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return str(value)

    return f"{number:,.{decimals}f}"


def format_large_number(
    value: Any,
) -> str:
    """
    格式化大型數值。
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return str(value)

    abs_number = abs(number)

    if abs_number >= 1_000_000_000:
        return (
            f"{number / 1_000_000_000:,.2f}B"
        )

    if abs_number >= 1_000_000:
        return (
            f"{number / 1_000_000:,.2f}M"
        )

    if abs_number >= 1_000:
        return (
            f"{number / 1_000:,.2f}K"
        )

    return f"{number:,.2f}"


def print_candidate(
    rank: int,
    candidate,
) -> None:
    """
    印出單一 SCOUT 候選市場。
    """

    metrics = candidate.metrics

    scores = metrics.get(
        "scores",
        {},
    )

    print(
        f"{rank}. {candidate.symbol}"
    )

    print(
        "   Scout Score : "
        f"{candidate.score:.4f}"
    )

    print(
        "   Last Price  : "
        f"{format_number(
            metrics.get('last_price'),
            8,
        )}"
    )

    print(
        "   24H Change  : "
        f"{format_number(
            metrics.get('price_change_pct'),
            4,
        )}%"
    )

    print(
        "   24H Range   : "
        f"{format_number(
            metrics.get('range_pct'),
            4,
        )}%"
    )

    print(
        "   24H Volume  : "
        f"{format_large_number(
            metrics.get(
                'approx_quote_volume_24h'
            )
        )}"
    )

    print(
        "   Spread      : "
        f"{format_number(
            metrics.get('spread_pct'),
            6,
        )}%"
    )

    funding_rate = metrics.get(
        "funding_rate"
    )

    if funding_rate is not None:

        funding_percent = (
            float(funding_rate)
            * 100
        )

        print(
            "   Funding     : "
            f"{funding_percent:.6f}%"
        )

    else:

        print(
            "   Funding     : N/A"
        )

    print(
        "   Open Interest USD : "
        f"{format_large_number(
            metrics.get(
                'open_interest_usd'
            )
        )}"
    )

    print(
        "   Scores:"
    )

    print(
        "      Volume       : "
        f"{format_number(
            scores.get('volume'),
            4,
        )}"
    )

    print(
        "      Liquidity    : "
        f"{format_number(
            scores.get('liquidity'),
            4,
        )}"
    )

    print(
        "      Volatility   : "
        f"{format_number(
            scores.get('volatility'),
            4,
        )}"
    )

    print(
        "      Open Interest: "
        f"{format_number(
            scores.get('open_interest'),
            4,
        )}"
    )

    print(
        "      Activity     : "
        f"{format_number(
            scores.get('activity'),
            4,
        )}"
    )

    if candidate.reasons:

        print(
            "   Reasons:"
        )

        for reason in candidate.reasons:

            print(
                f"      - {reason}"
            )

    print()


async def main() -> int:
    """
    SCOUT 真實市場掃描測試。

    測試流程：

    ScoutAgent
        ↓
    ScoutScanner
        ↓
    OKX Public API
        ↓
    所有 USDT-SWAP
        ↓
    Top 10 Candidates
    """

    print(
        "=" * 70
    )

    print(
        "CODEX BOT - SCOUT LIVE TEST"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "Exchange    : OKX"
    )

    print(
        "Market Type : SWAP"
    )

    print(
        "Scan Mode   : ALL USDT-SWAP"
    )

    print(
        "API Mode    : PUBLIC / READ ONLY"
    )

    print()

    print(
        "Starting SCOUT market scan..."
    )

    print()

    context = MarketContext(
        symbol="MARKET",
        exchange="OKX",
        market_type="swap",
        timeframes=[],
        metadata={
            "test": True,
            "source": "test_scout.py",
        },
    )

    payload = ScoutInput(
        symbols=[]
    )

    agent = ScoutAgent()

    output = await agent.analyze(
        context=context,
        payload=payload,
    )

    print(
        "=" * 70
    )

    print(
        "SCOUT RESULT"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Status     : {output.status.value}"
    )

    print(
        f"Bias       : {output.bias.value}"
    )

    print(
        f"Confidence : {output.confidence:.4f}"
    )

    print(
        f"Summary    : {output.summary}"
    )

    print()

    if (
        output.status
        == AgentStatus.ERROR
    ):

        print(
            "SCOUT TEST FAILED"
        )

        print()

        error_type = (
            output.data.get(
                "error_type"
            )
        )

        error_message = (
            output.data.get(
                "error"
            )
        )

        print(
            f"Error Type : {error_type}"
        )

        print(
            f"Error      : {error_message}"
        )

        if output.errors:

            print()

            print(
                "Additional errors:"
            )

            for error in output.errors:

                print(
                    f"- {error}"
                )

        return 1

    candidates = (
        output.candidates
    )

    if not candidates:

        print(
            "No candidates returned."
        )

        return 1

    print(
        f"Candidates : {len(candidates)}"
    )

    print()

    print(
        "=" * 70
    )

    print(
        "TOP MARKET OPPORTUNITIES"
    )

    print(
        "=" * 70
    )

    print()

    for (
        rank,
        candidate,
    ) in enumerate(
        candidates,
        start=1,
    ):

        print_candidate(
            rank=rank,
            candidate=candidate,
        )

    print(
        "=" * 70
    )

    print(
        "SCAN METADATA"
    )

    print(
        "=" * 70
    )

    print()

    for (
        key,
        value,
    ) in output.data.items():

        print(
            f"{key}: {value}"
        )

    print()

    print(
        "=" * 70
    )

    print(
        "SCOUT LIVE TEST COMPLETED"
    )

    print(
        "=" * 70
    )

    return 0


if __name__ == "__main__":

    try:

        exit_code = asyncio.run(
            main()
        )

        raise SystemExit(
            exit_code
        )

    except KeyboardInterrupt:

        print()

        print(
            "SCOUT test interrupted."
        )

        raise SystemExit(
            130
        )
