from __future__ import annotations

import asyncio

from app.agents.models import (
    MarketContext,
    TradeBias,
)

from app.agents.risk import (
    OpenPosition,
    ProposedTrade,
    RiskInput,
    RiskService,
    RiskVerdict,
)


async def main(
) -> int:

    context = MarketContext(
        symbol=(
            "UNI-USDT-SWAP"
        ),

        exchange="OKX",

        market_type="swap",
    )

    payload = RiskInput(
        account_equity=10000.0,

        available_balance=7000.0,

        daily_pnl=-100.0,

        open_positions=[
            OpenPosition(
                symbol=(
                    "BTC-USDT-SWAP"
                ),

                side=(
                    TradeBias.LONG
                ),

                notional_usdt=1500.0,

                leverage=3.0,
            )
        ],

        proposed_trade=(
            ProposedTrade(
                symbol=(
                    "UNI-USDT-SWAP"
                ),

                side=(
                    TradeBias.SHORT
                ),

                entry_price=8.00,

                current_price=7.98,

                stop_loss=8.20,

                take_profit=7.40,

                leverage=4.0,

                notional_usdt=1200.0,
            )
        ),
    )

    charts = {
        "bias":
            "short",

        "confidence":
            0.78,

        "volatility_regime":
            "normal",
    }

    sentiment = {
        "bias":
            "neutral",

        "crowding_side":
            "balanced",

        "metrics": {
            "crowding_score":
                0.35,
        },
    }

    news = {
        "bias":
            "neutral",

        "events": [],
    }

    service = RiskService()

    output = (
        await service.analyze(
            context=context,

            payload=payload,

            charts_result=charts,

            sentiment_result=(
                sentiment
            ),

            news_result=news,
        )
    )

    print(
        "Status:",
        output.status.value,
    )

    print(
        "Verdict:",
        output.verdict.value,
    )

    print(
        "Approved:",
        output.approved,
    )

    print(
        "Confidence:",
        output.confidence,
    )

    print(
        "Risk %:",
        output.metrics
        .risk_pct_equity,
    )

    print(
        "R/R:",
        output.metrics
        .risk_reward_ratio,
    )

    print(
        "Recommended notional:",
        output.metrics
        .recommended_notional_usdt,
    )

    print(
        "Checks:"
    )

    for check in output.checks:

        print(
            "-",
            check.name,
            check.passed,
            check.severity.value,
            check.reason,
        )

    if (
        output.verdict
        not in (
            RiskVerdict.APPROVE,
            RiskVerdict.REDUCE,
        )
    ):

        return 1

    return 0


if __name__ == "__main__":

    raise SystemExit(
        asyncio.run(
            main()
        )
    )
