from __future__ import annotations

import os

from pathlib import (
    Path,
)

from fastapi import (
    FastAPI,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from fastapi.responses import (
    FileResponse,
)

from .api import (
    router,
)


def _cors_origins(
) -> list[
    str
]:
    """
    Allowed frontend origins.

    Local:
        http://127.0.0.1:8000
        http://localhost:8000
        http://127.0.0.1:5500
        http://localhost:5500

    GitHub Pages:
        https://stun0019.github.io

    Production override:

        CODEX_CORS_ORIGINS=
        https://stun0019.github.io,
        https://example.com
    """

    raw = (
        os.getenv(
            "CODEX_CORS_ORIGINS",
            "",
        )
        .strip()
    )

    if raw:

        return [
            origin.strip()

            for origin
            in raw.split(",")

            if origin.strip()
        ]

    return [
        "http://127.0.0.1:8000",
        "http://localhost:8000",

        "http://127.0.0.1:5500",
        "http://localhost:5500",

        "https://stun0019.github.io",
    ]


app = FastAPI(
    title="Codex Bot API",

    version="0.1.0",

    docs_url="/docs",

    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=(
        _cors_origins()
    ),

    allow_credentials=False,

    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],

    allow_headers=[
        "Content-Type",
    ],
)


app.include_router(
    router
)


# =====================================
# FRONTEND
# =====================================

_REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


_INDEX_FILE = (
    _REPO_ROOT
    /
    "index.html"
)


@app.get(
    "/",
    include_in_schema=False,
)
async def dashboard():

    if (
        _INDEX_FILE
        .is_file()
    ):

        return FileResponse(
            _INDEX_FILE
        )

    return {
        "service":
            "codex-bot",

        "status":
            "ok",

        "dashboard":
            "index.html not found",

        "docs":
            "/docs",
    }
