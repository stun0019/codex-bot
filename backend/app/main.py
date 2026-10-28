from __future__ import annotations

import os

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .api import router


def _cors_origins() -> list[str]:
    """
    Build the CORS allow-list.

    GitHub Pages:
        https://stun0019.github.io

    Local development:
        http://127.0.0.1:8000
        http://localhost:8000
        http://127.0.0.1:5500
        http://localhost:5500

    Optional production additions:

        CODEX_CORS_ORIGINS=
        https://example.com,
        https://www.example.com

    Important:
        Environment variables ADD origins.
        They do not replace the default origins.
    """

    defaults = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://stun0019.github.io",
    ]

    raw = os.getenv(
        "CODEX_CORS_ORIGINS",
        "",
    ).strip()

    extras: list[str] = []

    if raw:
        extras = [
            origin.strip().rstrip("/")
            for origin in raw.split(",")
            if origin.strip()
        ]

    origins: list[str] = []

    for origin in [
        *defaults,
        *extras,
    ]:
        normalized = origin.strip().rstrip("/")

        if (
            normalized
            and
            normalized not in origins
        ):
            origins.append(
                normalized
            )

    return origins


app = FastAPI(
    title="Codex Bot API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# =====================================
# CORS
# =====================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=_cors_origins(),

    allow_credentials=False,

    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],

    allow_headers=[
        "Content-Type",
        "Accept",
        "Origin",
    ],

    expose_headers=[],

    max_age=86400,
)


# =====================================
# API ROUTES
# =====================================

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
    """
    Serve the local dashboard when the backend
    is opened directly.

    GitHub Pages users will normally load
    index.html from GitHub Pages instead.
    """

    if _INDEX_FILE.is_file():
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


# =====================================
# DEBUG / CORS INFO
# =====================================

@app.get(
    "/api/cors",
    include_in_schema=False,
)
async def cors_info():
    """
    Temporary diagnostic endpoint.

    Useful for confirming what origins
    Render is actually allowing.
    """

    return {
        "status":
            "ok",

        "allowed_origins":
            _cors_origins(),

        "github_pages_origin":
            "https://stun0019.github.io",
    }
