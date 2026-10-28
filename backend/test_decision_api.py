from __future__ import annotations

import asyncio

import httpx

from app.main import (
    app,
)


async def main(
) -> int:

    transport = (
        httpx.ASGITransport(
            app=app
        )
    )

    async with httpx.AsyncClient(
        transport=transport,

        base_url=(
            "http://test"
        ),
    ) as client:

        response = (
            await client.post(
                "/api/decision",

                json={
                    "context": {
                        "symbol":
                            "UNI-USDT-SWAP",

                        "timeframes": [
                            "15m",
                            "1H",
                            "4H",
                        ],
                    },

                    "payload": {
                        "charts_result": {
                            "status":
                                "success",

                            "symbol":
                                "UNI-USDT-SWAP",

                            "bias":
                                "short",

                            "confidence":
                                0.85,

                            "composite_score":
                                -0.72,

                            "data_quality_score":
                                0.92,

                            "disagreement_score":
                                0.05,

                            "timeframe_analyses": {
                                "4H": {
                                    "bias":
                                        "short",

                                    "score":
                                        -0.80
                                },

                                "1H": {
                                    "bias":
                                        "short",

                                    "score":
                                        -0.68
                                },

                                "15m": {
                                    "bias":
                                        "short",

                                    "score":
                                        -0.45
                                }
                            }
                        },

                        "sentiment_result": {
                            "status":
                                "success",

                            "symbol":
                                "UNI-USDT-SWAP",

                            "bias":
                                "short",

                            "confidence":
                                0.60,

                            "crowding_side":
                                "balanced",

                            "metrics": {
                                "composite_score":
                                    -0.30,

                                "crowding_score":
                                    0.25,

                                "data_quality_score":
                                    0.85,

                                "disagreement_score":
                                    0.10
                            }
                        },

                        "news_result": {
                            "status":
                                "success",

                            "symbol":
                                "UNI-USDT-SWAP",

                            "bias":
                                "neutral",

                            "confidence":
                                0.55,

                            "events": [],

                            "data": {
                                "source_articles":
                                    5
                            }
                        },

                        "risk_result": {
                            "status":
                                "success",

                            "symbol":
                                "UNI-USDT-SWAP",

                            "approved":
                                True,

                            "verdict":
                                "approve",

                            "confidence":
                                0.90,

                            "metrics": {
                                "recommended_notional_usdt":
                                    1000
                            }
                        },

                        "proposed_trade": {
                            "symbol":
                                "UNI-USDT-SWAP",

                            "side":
                                "short",

                            "entry_price":
                                8.0,

                            "stop_loss":
                                8.2,

                            "take_profit":
                                7.4,

                            "leverage":
                                4,

                            "notional_usdt":
                                1200
                        }
                    },

                    "enrich":
                        False,

                    "include_scout":
                        False,

                    "include_news":
                        False
                }
            )
        )

        assert (
            response.status_code
            ==
            200
        )

        payload = (
            response.json()
        )

        decision = (
            payload[
                "decision"
            ]
        )

        print(
            decision
        )

        assert (
            decision[
                "status"
            ]
            ==
            "success"
        )

        assert (
            decision[
                "bias"
            ]
            ==
            "short"
        )

        assert (
            decision[
                "directional_bias"
            ]
            ==
            "short"
        )

        assert (
            decision[
                "risk_approved"
            ]
            is True
        )

    print(
        "DECISION API: PASS"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        asyncio.run(
            main()
        )
    )
