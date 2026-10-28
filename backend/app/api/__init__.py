from fastapi import (
    APIRouter,
)

from .routes import (
    router as core_router,
)

from .decision import (
    router as decision_router,
)


router = APIRouter()

router.include_router(
    core_router
)

router.include_router(
    decision_router
)


__all__ = [
    "router",
]
