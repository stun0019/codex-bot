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
        base_url="http://test",
    ) as client:

        # =============================
        # Health
        # =============================

        health = (
            await client.get(
                "/api/health"
            )
        )

        assert (
            health.status_code
            ==
            200
        )

        assert (
            health.json()[
                "agents_ready"
            ]
            ==
            5
        )

        # =============================
        # Agents
        # =============================

        agents = (
            await client.get(
                "/api/agents"
            )
        )

        assert (
            agents.status_code
            ==
            200
        )

        assert (
            agents.json()[
                "total"
            ]
            ==
            6
        )

        # =============================
        # Risk symbol mismatch
        # =============================

        mismatch = (
            await client.post(
                "/api/risk",

                json={
                    "context": {
                        "symbol":
                            "BTC-USDT-SWAP",
                    },

                    "payload": {
                        "account_equity":
                            10000.0,

                        "available_balance":
                            8000.0,

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
                                3.0,

                            "notional_usdt":
                                1000.0,
                        },
                    },

                    "enrich":
                        False,
                },
            )
        )

        assert (
            mismatch.status_code
            ==
            200
        )

        payload = (
            mismatch.json()
        )

        assert (
            payload[
                "risk"
            ][
                "status"
            ]
            ==
            "error"
        )

        assert (
            payload[
                "risk"
            ][
                "data"
            ][
                "reason"
            ]
            ==
            "symbol_mismatch"
        )

        # =============================
        # Valid risk
        # =============================

        approved = (
            await client.post(
                "/api/risk",

                json={
                    "context": {
                        "symbol":
                            "UNI-USDT-SWAP",
                    },

                    "payload": {
                        "account_equity":
                            10000.0,

                        "available_balance":
                            8000.0,

                        "proposed_trade": {
                            "symbol":
                                "UNI-USDT-SWAP",

                            "side":
                                "long",

                            "entry_price":
                                10.0,

                            "stop_loss":
                                9.8,

                            "take_profit":
                                10.4,

                            "leverage":
                                3.0,

                            "notional_usdt":
                                1000.0,
                        },
                    },

                    "enrich":
                        False,
                },
            )
        )

        assert (
            approved.status_code
            ==
            200
        )

        approved_payload = (
            approved.json()
        )

        assert (
            approved_payload[
                "risk"
            ][
                "status"
            ]
            ==
            "success"
        )

        assert (
            approved_payload[
                "risk"
            ][
                "verdict"
            ]
            ==
            "approve"
        )

    print(
        "API: PASS"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        asyncio.run(
            main()
        )
    )
