from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
)

from ..models import (
    MarketContext,
)

from .agent import (
    RiskAgent,
)

from .models import (
    RiskInput,
    RiskOutput,
)


class RiskService:
    """
    RISK orchestration layer.

    可以直接接：

        ChartsOutput
        SentimentOutput
        NewsOutput

    或普通 dict。
    """

    def __init__(
        self,
        agent: (
            RiskAgent
            | None
        ) = None,
    ) -> None:

        self.agent = (
            agent
            if agent is not None
            else RiskAgent()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: RiskInput,
        *,
        charts_result: Any = None,
        sentiment_result: Any = None,
        news_result: Any = None,
    ) -> RiskOutput:

        updates: dict[
            str,
            Any,
        ] = {}

        if charts_result is not None:

            updates[
                "charts_result"
            ] = (
                self._serialize(
                    charts_result
                )
            )

        if sentiment_result is not None:

            updates[
                "sentiment_result"
            ] = (
                self._serialize(
                    sentiment_result
                )
            )

        if news_result is not None:

            updates[
                "news_result"
            ] = (
                self._serialize(
                    news_result
                )
            )

        if updates:

            payload = (
                payload.model_copy(
                    update=updates,
                    deep=True,
                )
            )

        return (
            await self.agent.analyze(
                context=context,
                payload=payload,
            )
        )

    @staticmethod
    def _serialize(
        value: Any,
    ) -> dict[
        str,
        Any,
    ]:

        if isinstance(
            value,
            BaseModel,
        ):

            return value.model_dump(
                mode="json"
            )

        if isinstance(
            value,
            dict,
        ):

            return dict(
                value
            )

        raise TypeError(
            (
                "Agent result must be "
                "a Pydantic model or dict."
            )
        )
