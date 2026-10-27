from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import AgentOutput


class RiskInput(BaseModel):
    account_equity: float | None = None

    available_balance: float | None = None

    open_positions: list[
        dict[str, Any]
    ] = Field(default_factory=list)

    proposed_trade: dict[str, Any] = Field(
        default_factory=dict
    )

    risk_limits: dict[str, Any] = Field(
        default_factory=dict
    )


class RiskCheck(BaseModel):
    name: str

    passed: bool

    reason: str = ""

    value: Any | None = None

    limit: Any | None = None


class RiskOutput(AgentOutput):
    approved: bool = False

    checks: list[RiskCheck] = Field(
        default_factory=list
    )

    proposed_position_size: float | None = None

    estimated_loss: float | None = None

    estimated_reward: float | None = None
