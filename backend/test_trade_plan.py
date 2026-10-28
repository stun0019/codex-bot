from __future__ import annotations

from app.agents.charts import (
    ChartsOutput,
    TimeframeAnalysis,
    TradePlanBuilder,
    TrendRegime,
    VolatilityRegime,
)

from app.agents.models import (
    AgentName,
    AgentStatus,
    TradeBias,
)


def analysis(
    timeframe: str,
    bias: TradeBias,
    close: float,
    support: float,
    resistance: float,
    atr: float,
    confidence: float = 0.80,
) -> TimeframeAnalysis:

    return TimeframeAnalysis(
        timeframe=timeframe,

        candle_count=200,

        bias=bias,

        score=(
            0.70
            if bias
            ==
            TradeBias.LONG
            else -0.70
        ),

        confidence=confidence,

        trend_regime=(
            TrendRegime.UPTREND
            if bias
            ==
            TradeBias.LONG
            else
            TrendRegime.DOWNTREND
        ),

        volatility_regime=(
            VolatilityRegime.NORMAL
        ),

        indicators={
            "latest_close":
                close,

            "atr": {
                "value":
                    atr,

                "percent":
                    atr
                    /
                    close
                    *
                    100.0,
            },
        },

        market_structure={
            "support_resistance": {
                "current_price":
                    close,

                "support":
                    support,

                "resistance":
                    resistance,
            }
        },

        data_quality_score=0.95,

        disagreement_score=0.05,
    )


def test_long(
) -> None:

    output = ChartsOutput(
        agent=AgentName.CHARTS,

        status=AgentStatus.SUCCESS,

        symbol="ENA-USDT-SWAP",

        bias=TradeBias.LONG,

        confidence=0.82,

        summary="test",

        composite_score=0.70,

        trend_regime=(
            TrendRegime.UPTREND
        ),

        volatility_regime=(
            VolatilityRegime.NORMAL
        ),

        primary_timeframe="4H",

        timeframe_analyses={
            "4H":
                analysis(
                    "4H",
                    TradeBias.LONG,
                    0.3200,
                    0.2950,
                    0.3600,
                    0.008,
                ),

            "1H":
                analysis(
                    "1H",
                    TradeBias.LONG,
                    0.3200,
                    0.3050,
                    0.3500,
                    0.005,
                ),

            "15m":
                analysis(
                    "15m",
                    TradeBias.LONG,
                    0.3200,
                    0.3120,
                    0.3350,
                    0.004,
                ),
        },

        data_quality_score=0.95,

        disagreement_score=0.05,
    )

    plan = (
        TradePlanBuilder()
        .build(
            output
        )
    )

    assert plan is not None

    assert (
        plan.side
        ==
        TradeBias.LONG
    )

    assert (
        plan.stop_loss
        <
        plan.entry_price
        <
        plan.take_profit
    )

    assert (
        plan.risk_reward_ratio
        >=
        2.0
    )

    print(
        plan.model_dump(
            mode="json"
        )
    )


def test_countertrend_wait(
) -> None:

    output = ChartsOutput(
        agent=AgentName.CHARTS,

        status=AgentStatus.SUCCESS,

        symbol="UNI-USDT-SWAP",

        bias=TradeBias.SHORT,

        confidence=0.80,

        summary="test",

        composite_score=-0.70,

        trend_regime=(
            TrendRegime.DOWNTREND
        ),

        volatility_regime=(
            VolatilityRegime.NORMAL
        ),

        primary_timeframe="4H",

        timeframe_analyses={
            "4H":
                analysis(
                    "4H",
                    TradeBias.SHORT,
                    8.0,
                    7.2,
                    8.5,
                    0.20,
                ),

            "1H":
                analysis(
                    "1H",
                    TradeBias.SHORT,
                    8.0,
                    7.4,
                    8.3,
                    0.15,
                ),

            # 15m 正在反彈。
            "15m":
                analysis(
                    "15m",
                    TradeBias.LONG,
                    8.0,
                    7.8,
                    8.2,
                    0.10,
                ),
        },

        data_quality_score=0.95,

        disagreement_score=0.10,
    )

    plan = (
        TradePlanBuilder()
        .build(
            output
        )
    )

    assert plan is None


if __name__ == "__main__":

    test_long()

    test_countertrend_wait()

    print(
        "TRADE PLAN: PASS"
    )
