from __future__ import annotations

import asyncio

from app.agents.models import (
    AgentStatus,
    MarketContext,
    TradeBias,
)

from app.agents.risk import (
    ProposedTrade,
    RiskAgent,
    RiskInput,
    RiskVerdict,
)


def context(
) -> MarketContext:

    return MarketContext(
        symbol=(
            "UNI-USDT-SWAP"
        ),

        exchange="OKX",

        market_type="swap",
    )


async def test_approve(
) -> bool:

    output = (
        await RiskAgent()
        .analyze(
            context=context(),

            payload=RiskInput(
                account_equity=10000.0,

                available_balance=8000.0,

                daily_pnl=0.0,

                proposed_trade=(
                    ProposedTrade(
                        symbol=(
                            "UNI-USDT-SWAP"
                        ),

                        side=(
                            TradeBias.LONG
                        ),

                        entry_price=10.0,

                        stop_loss=9.8,

                        take_profit=10.4,

                        leverage=3.0,

                        notional_usdt=(
                            1000.0
                        ),
                    )
                ),
            ),
        )
    )

    print(
        "APPROVE:",
        output.verdict,
        output.metrics,
    )

    return (
        output.status
        ==
        AgentStatus.SUCCESS
        and
        output.verdict
        ==
        RiskVerdict.APPROVE
        and
        output.approved
    )


async def test_reject_risk(
) -> bool:

    output = (
        await RiskAgent()
        .analyze(
            context=context(),

            payload=RiskInput(
                account_equity=10000.0,

                available_balance=8000.0,

                proposed_trade=(
                    ProposedTrade(
                        symbol=(
                            "UNI-USDT-SWAP"
                        ),

                        side=(
                            TradeBias.LONG
                        ),

                        entry_price=10.0,

                        stop_loss=9.0,

                        take_profit=12.0,

                        leverage=5.0,

                        notional_usdt=(
                            5000.0
                        ),
                    )
                ),
            ),
        )
    )

    print(
        "REJECT:",
        output.verdict,
        output.data.get(
            "failed_checks"
        ),
    )

    return (
        output.verdict
        ==
        RiskVerdict.REJECT
        and
        not output.approved
    )


async def test_reduce_rr(
) -> bool:

    output = (
        await RiskAgent()
        .analyze(
            context=context(),

            payload=RiskInput(
                account_equity=10000.0,

                available_balance=8000.0,

                proposed_trade=(
                    ProposedTrade(
                        symbol=(
                            "UNI-USDT-SWAP"
                        ),

                        side=(
                            TradeBias.LONG
                        ),

                        entry_price=10.0,

                        stop_loss=9.8,

                        take_profit=10.1,

                        leverage=3.0,

                        notional_usdt=(
                            1000.0
                        ),
                    )
                ),
            ),
        )
    )

    print(
        "LOW RR:",
        output.verdict,
        output.metrics
        .risk_reward_ratio,
    )

    return (
        output.verdict
        ==
        RiskVerdict.REDUCE
    )


async def test_charts_opposition(
) -> bool:

    output = (
        await RiskAgent()
        .analyze(
            context=context(),

            payload=RiskInput(
                account_equity=10000.0,

                available_balance=8000.0,

                proposed_trade=(
                    ProposedTrade(
                        symbol=(
                            "UNI-USDT-SWAP"
                        ),

                        side=(
                            TradeBias.LONG
                        ),

                        entry_price=10.0,

                        stop_loss=9.8,

                        take_profit=10.5,

                        leverage=3.0,

                        notional_usdt=(
                            1000.0
                        ),
                    )
                ),

                charts_result={
                    "bias":
                        "short",

                    "confidence":
                        0.90,

                    "volatility_regime":
                        "normal",
                },
            ),
        )
    )

    print(
        "CHARTS OPPOSITION:",
        output.verdict,
    )

    return (
        output.verdict
        ==
        RiskVerdict.REDUCE
    )


async def test_empty(
) -> bool:

    output = (
        await RiskAgent()
        .analyze(
            context=context(),
            payload=RiskInput(),
        )
    )

    return (
        output.status
        ==
        AgentStatus.SKIPPED
    )


async def main(
) -> int:

    tests = [
        await test_approve(),
        await test_reject_risk(),
        await test_reduce_rr(),
        await test_charts_opposition(),
        await test_empty(),
    ]

    passed = sum(
        1
        for test
        in tests
        if test
    )

    print(
        f"RISK: {passed}/{len(tests)}"
    )

    return (
        0
        if all(tests)
        else 1
    )


if __name__ == "__main__":

    raise SystemExit(
        asyncio.run(
            main()
        )
    )
