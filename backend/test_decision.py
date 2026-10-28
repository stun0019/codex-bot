from __future__ import annotations

import asyncio

from app.agents.decision import (
    DecisionAgent,
    DecisionInput,
)

from app.agents.models import (
    AgentStatus,
    MarketContext,
    TradeBias,
)

from app.agents.risk import (
    ProposedTrade,
)


SYMBOL = "UNI-USDT-SWAP"


def context(
) -> MarketContext:

    return MarketContext(
        symbol=SYMBOL,

        exchange="OKX",

        market_type="swap",

        timeframes=[
            "15m",
            "1H",
            "4H",
        ],
    )


def long_charts(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "bias":
            "long",

        "confidence":
            0.82,

        "composite_score":
            0.72,

        "data_quality_score":
            0.92,

        "disagreement_score":
            0.08,

        "timeframe_analyses": {
            "4H": {
                "bias":
                    "long",

                "score":
                    0.78,

                "confidence":
                    0.88,
            },

            "1H": {
                "bias":
                    "long",

                "score":
                    0.68,

                "confidence":
                    0.82,
            },

            "15m": {
                "bias":
                    "long",

                "score":
                    0.42,

                "confidence":
                    0.70,
            },
        },
    }


def short_charts(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "bias":
            "short",

        "confidence":
            0.84,

        "composite_score":
            -0.74,

        "data_quality_score":
            0.93,

        "disagreement_score":
            0.07,

        "timeframe_analyses": {
            "4H": {
                "bias":
                    "short",

                "score":
                    -0.80,

                "confidence":
                    0.90,
            },

            "1H": {
                "bias":
                    "short",

                "score":
                    -0.70,

                "confidence":
                    0.84,
            },

            "15m": {
                "bias":
                    "short",

                "score":
                    -0.45,

                "confidence":
                    0.72,
            },
        },
    }


def bullish_sentiment(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "bias":
            "long",

        "confidence":
            0.65,

        "crowding_side":
            "balanced",

        "metrics": {
            "composite_score":
                0.35,

            "crowding_score":
                0.32,

            "data_quality_score":
                0.85,

            "disagreement_score":
                0.10,
        },
    }


def bearish_sentiment(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "bias":
            "short",

        "confidence":
            0.68,

        "crowding_side":
            "balanced",

        "metrics": {
            "composite_score":
                -0.38,

            "crowding_score":
                0.36,

            "data_quality_score":
                0.86,

            "disagreement_score":
                0.09,
        },
    }


def bullish_news(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "bias":
            "long",

        "confidence":
            0.70,

        "events": [
            {
                "title":
                    "Positive catalyst",

                "affected_symbols": [
                    SYMBOL
                ],

                "bias":
                    "long",

                "impact_score":
                    0.75,

                "confidence":
                    0.80,
            }
        ],

        "data": {
            "source_articles":
                10,
        },
    }


def bearish_news(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "bias":
            "short",

        "confidence":
            0.72,

        "events": [
            {
                "title":
                    "Negative catalyst",

                "affected_symbols": [
                    SYMBOL
                ],

                "bias":
                    "short",

                "impact_score":
                    0.78,

                "confidence":
                    0.82,
            }
        ],

        "data": {
            "source_articles":
                10,
        },
    }


def approved_risk(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "approved":
            True,

        "verdict":
            "approve",

        "confidence":
            0.90,

        "metrics": {
            "recommended_notional_usdt":
                900.0,

            "risk_pct_equity":
                1.0,

            "risk_reward_ratio":
                2.5,
        },
    }


def rejected_risk(
) -> dict:

    return {
        "status":
            "success",

        "symbol":
            SYMBOL,

        "approved":
            False,

        "verdict":
            "reject",

        "confidence":
            0.90,
    }


async def test_long(
) -> bool:

    trade = ProposedTrade(
        symbol=SYMBOL,

        side=TradeBias.LONG,

        entry_price=10.0,

        stop_loss=9.7,

        take_profit=10.8,

        leverage=3,

        notional_usdt=1000,
    )

    output = (
        await DecisionAgent()
        .analyze(
            context=context(),

            payload=DecisionInput(
                charts_result=(
                    long_charts()
                ),

                sentiment_result=(
                    bullish_sentiment()
                ),

                news_result=(
                    bullish_news()
                ),

                risk_result=(
                    approved_risk()
                ),

                proposed_trade=trade,
            ),
        )
    )

    print(
        "LONG:",
        output.bias,
        output.directional_bias,
        output.confidence,
    )

    return (
        output.status
        ==
        AgentStatus.SUCCESS
        and
        output.bias
        ==
        TradeBias.LONG
        and
        output.directional_bias
        ==
        TradeBias.LONG
        and
        output.risk_approved
    )


async def test_short(
) -> bool:

    trade = ProposedTrade(
        symbol=SYMBOL,

        side=TradeBias.SHORT,

        entry_price=10.0,

        stop_loss=10.3,

        take_profit=9.2,

        leverage=3,

        notional_usdt=1000,
    )

    output = (
        await DecisionAgent()
        .analyze(
            context=context(),

            payload=DecisionInput(
                charts_result=(
                    short_charts()
                ),

                sentiment_result=(
                    bearish_sentiment()
                ),

                news_result=(
                    bearish_news()
                ),

                risk_result=(
                    approved_risk()
                ),

                proposed_trade=trade,
            ),
        )
    )

    print(
        "SHORT:",
        output.bias,
        output.confidence,
    )

    return (
        output.bias
        ==
        TradeBias.SHORT
        and
        output.directional_bias
        ==
        TradeBias.SHORT
    )


async def test_risk_reject_wait(
) -> bool:

    trade = ProposedTrade(
        symbol=SYMBOL,

        side=TradeBias.LONG,

        entry_price=10.0,

        stop_loss=9.7,

        take_profit=10.8,

        leverage=3,

        notional_usdt=1000,
    )

    output = (
        await DecisionAgent()
        .analyze(
            context=context(),

            payload=DecisionInput(
                charts_result=(
                    long_charts()
                ),

                sentiment_result=(
                    bullish_sentiment()
                ),

                news_result=(
                    bullish_news()
                ),

                risk_result=(
                    rejected_risk()
                ),

                proposed_trade=trade,
            ),
        )
    )

    print(
        "RISK REJECT:",
        output.bias,
    )

    return (
        output.bias
        ==
        TradeBias.WAIT
        and
        output.directional_bias
        ==
        TradeBias.LONG
    )


async def test_entry_pullback_wait(
) -> bool:

    charts = (
        short_charts()
    )

    charts[
        "timeframe_analyses"
    ][
        "15m"
    ] = {
        "bias":
            "long",

        "score":
            0.40,

        "confidence":
            0.70,
    }

    trade = ProposedTrade(
        symbol=SYMBOL,

        side=TradeBias.SHORT,

        entry_price=10.0,

        stop_loss=10.3,

        take_profit=9.2,

        leverage=3,

        notional_usdt=1000,
    )

    output = (
        await DecisionAgent()
        .analyze(
            context=context(),

            payload=DecisionInput(
                charts_result=charts,

                sentiment_result=(
                    bearish_sentiment()
                ),

                news_result=(
                    bearish_news()
                ),

                risk_result=(
                    approved_risk()
                ),

                proposed_trade=trade,
            ),
        )
    )

    print(
        "15M COUNTERTREND:",
        output.bias,
        output.directional_bias,
    )

    return (
        output.bias
        ==
        TradeBias.WAIT
        and
        output.directional_bias
        ==
        TradeBias.SHORT
    )


async def test_htf_conflict_wait(
) -> bool:

    charts = (
        long_charts()
    )

    charts[
        "timeframe_analyses"
    ][
        "1H"
    ] = {
        "bias":
            "short",

        "score":
            -0.55,

        "confidence":
            0.75,
    }

    trade = ProposedTrade(
        symbol=SYMBOL,

        side=TradeBias.LONG,

        entry_price=10,

        stop_loss=9.7,

        take_profit=10.8,

        leverage=3,

        notional_usdt=1000,
    )

    output = (
        await DecisionAgent()
        .analyze(
            context=context(),

            payload=DecisionInput(
                charts_result=charts,

                sentiment_result=(
                    bullish_sentiment()
                ),

                news_result=(
                    bullish_news()
                ),

                risk_result=(
                    approved_risk()
                ),

                proposed_trade=trade,
            ),
        )
    )

    return (
        output.bias
        ==
        TradeBias.WAIT
    )


async def test_symbol_mismatch(
) -> bool:

    trade = ProposedTrade(
        symbol=(
            "BTC-USDT-SWAP"
        ),

        side=TradeBias.LONG,

        entry_price=10,

        stop_loss=9.7,

        take_profit=10.8,

        leverage=3,

        notional_usdt=1000,
    )

    output = (
        await DecisionAgent()
        .analyze(
            context=context(),

            payload=DecisionInput(
                charts_result=(
                    long_charts()
                ),

                proposed_trade=trade,

                require_risk_approval=False,
            ),
        )
    )

    print(
        "MISMATCH:",
        output.status,
    )

    return (
        output.status
        ==
        AgentStatus.ERROR
        and
        output.bias
        ==
        TradeBias.WAIT
    )


async def main(
) -> int:

    tests = [
        await test_long(),
        await test_short(),
        await test_risk_reject_wait(),
        await test_entry_pullback_wait(),
        await test_htf_conflict_wait(),
        await test_symbol_mismatch(),
    ]

    passed = sum(
        bool(
            test
        )
        for test
        in tests
    )

    print(
        (
            "DECISION: "
            f"{passed}/{len(tests)}"
        )
    )

    return (
        0
        if all(
            tests
        )
        else 1
    )


if __name__ == "__main__":

    raise SystemExit(
        asyncio.run(
            main()
        )
    )
