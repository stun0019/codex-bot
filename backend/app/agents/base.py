from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from .models import AgentName, MarketContext


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(
    ABC,
    Generic[InputT, OutputT],
):
    """
    所有 AI Agent 的共同基底。

    目前不直接綁定 OpenAI API。
    未來可以在這層加入：

    - OpenAI client
    - logging
    - timeout
    - retry
    - tracing
    - metrics
    - token usage
    - prompt version
    """

    name: AgentName

    def __init__(self) -> None:
        if not hasattr(self, "name"):
            raise ValueError(
                f"{self.__class__.__name__} must define agent name"
            )

    @abstractmethod
    async def analyze(
        self,
        context: MarketContext,
        payload: InputT,
    ) -> OutputT:
        """
        執行 Agent 分析。

        每個 Agent 必須自行實作。
        """
        raise NotImplementedError
