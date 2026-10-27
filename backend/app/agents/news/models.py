from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models import AgentOutput


class NewsArticle(BaseModel):
    title: str

    source: str

    published_at: datetime | None = None

    url: str | None = None

    content: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class NewsInput(BaseModel):
    articles: list[NewsArticle] = Field(
        default_factory=list
    )


class NewsEvent(BaseModel):
    title: str

    category: str | None = None

    affected_symbols: list[str] = Field(
        default_factory=list
    )

    impact_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    description: str = ""


class NewsOutput(AgentOutput):
    events: list[NewsEvent] = Field(
        default_factory=list
    )
