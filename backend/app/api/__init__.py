from fastapi import (
    APIRouter,
)

from .routes import (
    router as core_router,
)

from .decision import (
    router as decision_router,
)

from .opportunities import (
    router as opportunities_router,
)


router = APIRouter()

router.include_router(
    core_router
)

router.include_router(
    decision_router
)

router.include_router(
    opportunities_router
)


__all__ = [
    "router",
]
