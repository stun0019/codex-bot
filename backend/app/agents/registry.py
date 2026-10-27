from __future__ import annotations

from .base import BaseAgent
from .models import AgentName

from .scout import ScoutAgent
from .news import NewsAgent
from .sentiment import SentimentAgent
from .charts import ChartsAgent
from .risk import RiskAgent
from .decision import DecisionAgent


class AgentRegistry:
    """
    統一管理系統內的 AI Agent。

    功能：
    - 註冊 Agent
    - 取得指定 Agent
    - 取得全部 Agent
    - 檢查 Agent 是否已註冊
    """

    def __init__(self) -> None:
        self._agents: dict[AgentName, BaseAgent] = {}

    def register(
        self,
        agent: BaseAgent,
    ) -> None:
        """
        註冊一個 Agent。

        如果同名 Agent 已存在，會直接覆蓋。
        """
        self._agents[agent.name] = agent

    def get(
        self,
        name: AgentName,
    ) -> BaseAgent:
        """
        取得指定 Agent。

        若 Agent 尚未註冊，拋出 KeyError。
        """
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(
                f"Agent not registered: {name}"
            ) from exc

    def has(
        self,
        name: AgentName,
    ) -> bool:
        """
        檢查指定 Agent 是否已註冊。
        """
        return name in self._agents

    def all(
        self,
    ) -> dict[AgentName, BaseAgent]:
        """
        回傳所有已註冊 Agent。

        回傳副本，避免外部直接修改 registry 內容。
        """
        return self._agents.copy()

    def names(
        self,
    ) -> list[AgentName]:
        """
        回傳所有已註冊 Agent 名稱。
        """
        return list(self._agents.keys())


def create_default_registry() -> AgentRegistry:
    """
    建立 codex-bot 預設 Agent Registry。

    預設註冊六個 Agent：
    - Scout
    - News
    - Sentiment
    - Charts
    - Risk
    - Decision
    """

    registry = AgentRegistry()

    registry.register(ScoutAgent())
    registry.register(NewsAgent())
    registry.register(SentimentAgent())
    registry.register(ChartsAgent())
    registry.register(RiskAgent())
    registry.register(DecisionAgent())

    return registry
