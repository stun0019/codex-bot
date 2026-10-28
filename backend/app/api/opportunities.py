from __future__ import annotations

from fastapi import (
    APIRouter,
)

from ..opportunities import (
    OpportunitiesOutput,
    OpportunitiesService,
    OpportunityScanInput,
)


router = APIRouter(
    prefix="/api",
    tags=[
        "opportunities",
    ],
)


@router.post(
    "/opportunities",
    response_model=(
        OpportunitiesOutput
    ),
)
async def opportunities(
    request: OpportunityScanInput,
) -> OpportunitiesOutput:
    """
    RUN ALL.

    User supplies only account state.

    System finds:

        Symbol
        Direction
        Entry
        Stop
        Target

    Flow:

        SCOUT
        ↓
        NEWS / SENTIMENT / CHARTS
        ↓
        TradePlan
        ↓
        RISK
        ↓
        DECISION
    """

    service = (
        OpportunitiesService()
    )

    return (
        await service.scan(
            request
        )
    )
