from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
)

from ..models import (
    MarketContext,
)

from ..risk.models import (
    ProposedTrade,
)

from .agent import (
    DecisionAgent,
)

from .models import (
    DecisionInput,
    DecisionOutput,
)


class DecisionService:
    """
    DECISION orchestration layer.

    Accepts either:

        Pydantic AgentOutput
        dict

    and converts everything into
    DecisionInput.
    """

    def __init__(
        self,
        agent: (
            DecisionAgent
            | None
        ) = None,
    ) -> None:

        self.agent = (
            agent
            if agent is not None
            else DecisionAgent()
        )

    async def analyze(
        self,
        context: MarketContext,
        payload: (
            DecisionInput
            | None
        ) = None,
        *,
        scout_result: Any = None,
        news_result: Any = None,
        sentiment_result: Any = None,
        charts_result: Any = None,
        risk_result: Any = None,
        proposed_trade: (
            ProposedTrade
            | None
        ) = None,
        require_risk_approval: (
            bool
            | None
        ) = None,
    ) -> DecisionOutput:

        if payload is None:

            payload = (
                DecisionInput()
            )

        updates: dict[
            str,
            Any,
        ] = {}

        if scout_result is not None:

            updates[
                "scout_result"
            ] = (
                self._serialize(
                    scout_result
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

        if sentiment_result is not None:

            updates[
                "sentiment_result"
            ] = (
                self._serialize(
                    sentiment_result
                )
            )

        if charts_result is not None:

            updates[
                "charts_result"
            ] = (
                self._serialize(
                    charts_result
                )
            )

        if risk_result is not None:

            updates[
                "risk_result"
            ] = (
                self._serialize(
                    risk_result
                )
            )

        if proposed_trade is not None:

            updates[
                "proposed_trade"
            ] = proposed_trade

        if (
            require_risk_approval
            is not None
        ):

            updates[
                "require_risk_approval"
            ] = (
                require_risk_approval
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
                "Decision source result "
                "must be a Pydantic "
                "model or dict."
            )
        )
