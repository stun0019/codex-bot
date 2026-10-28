from __future__ import annotations

import asyncio

from app.agents.decision import (
    DecisionInput,
    DecisionService,
)

from app.agents.models import (
    MarketContext,
    TradeBias,
)

from app.agents.risk import (
    ProposedTrade,
)


async def main(
) -> int:

    symbol = (
        "UNI-USDT-SWAP"
    )

    context = MarketContext(
        symbol=symbol,

        exchange="OKX",

        market_type="swap",

        timeframes=[
            "15m",
            "1H",
            "4H",
        ],
    )

    trade = ProposedTrade(
        symbol=symbol,

        side=(
            TradeBias.SHORT
        ),

        entry_price=8.00,

        stop_loss=8.20,

        take_profit=7.40,

        leverage=4.0,

        notional_usdt=1200.0,
    )

    charts = {
        "status":
            "success",

        "symbol":
            symbol,

        "bias":
            "short",

        "confidence":
            0.82,

        "composite_score":
            -0.70,

        "data_quality_score":
            0.91,

        "disagreement_score":
            0.08,

        "timeframe_analyses": {
            "4H": {
                "bias":
                    "short",

                "score":
                    -0.78,
            },

            "1H": {
                "bias":
                    "short",

                "score":
                    -0.65,
            },

            "15m": {
                "bias":
                    "short",

                "score":
                    -0.42,
            },
        },
    }

    sentiment = {
        "status":
            "success",

        "symbol":
            symbol,

        "bias":
            "short",

        "confidence":
            0.65,

        "crowding_side":
            "balanced",

        "metrics": {
            "composite_score":
                -0.32,

            "crowding_score":
                0.30,

            "data_quality_score":
                0.84,

            "disagreement_score":
                0.10,
        },
    }

    news = {
        "status":
            "success",

        "symbol":
            symbol,

        "bias":
            "neutral",

        "confidence":
            0.55,

        "events": [],

        "data": {
            "source_articles":
                8,
        },
    }

    risk = {
        "status":
            "success",

        "symbol":
            symbol,

        "approved":
            True,

        "verdict":
            "approve",

        "confidence":
            0.90,

        "metrics": {
            "recommended_notional_usdt":
                1000.0,

            "risk_pct_equity":
                1.0,

            "risk_reward_ratio":
                3.0,
        },
    }

    output = (
        await DecisionService()
        .analyze(
            context=context,

            payload=(
                DecisionInput()
            ),

            charts_result=charts,

            sentiment_result=(
                sentiment
            ),

            news_result=news,

            risk_result=risk,

            proposed_trade=trade,
        )
    )

    print(
        "Action:",
        output.bias.value,
    )

    print(
        "Directional bias:",
        output
        .directional_bias
        .value,
    )

    print(
        "Confidence:",
        output.confidence,
    )

    print(
        "Risk approved:",
        output.risk_approved,
    )

    print(
        "Position:",
        output
        .decision
        .position_size,
    )

    print(
        "Reasoning:"
    )

    for reason in (
        output
        .decision
        .reasoning
    ):

        print(
            "-",
            reason,
        )

    assert (
        output.bias
        ==
        TradeBias.SHORT
    )

    assert (
        output.risk_approved
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        asyncio.run(
            main()
        )
    )
