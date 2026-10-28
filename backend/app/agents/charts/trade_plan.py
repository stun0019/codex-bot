from __future__ import annotations

from dataclasses import dataclass

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from ..models import (
    AgentStatus,
    TradeBias,
)

from .models import (
    ChartsOutput,
    TimeframeAnalysis,
)


class TradePlan(
    BaseModel
):
    symbol: str

    side: TradeBias

    setup_type: str

    entry_timeframe: str = "15m"

    anchor_timeframes: list[str] = Field(
        default_factory=lambda: [
            "1H",
            "4H",
        ]
    )

    entry_price: float = Field(
        gt=0.0,
    )

    stop_loss: float = Field(
        gt=0.0,
    )

    take_profit: float = Field(
        gt=0.0,
    )

    invalidation_price: float = Field(
        gt=0.0,
    )

    risk_distance_pct: float = Field(
        gt=0.0,
    )

    reward_distance_pct: float = Field(
        gt=0.0,
    )

    risk_reward_ratio: float = Field(
        gt=0.0,
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    atr: float | None = Field(
        default=None,
        gt=0.0,
    )

    support: float | None = Field(
        default=None,
        gt=0.0,
    )

    resistance: float | None = Field(
        default=None,
        gt=0.0,
    )

    reasons: list[str] = Field(
        default_factory=list
    )

    @model_validator(
        mode="after"
    )
    def validate_prices(
        self,
    ) -> "TradePlan":

        if self.side == TradeBias.LONG:

            if not (
                self.stop_loss
                <
                self.entry_price
                <
                self.take_profit
            ):

                raise ValueError(
                    (
                        "LONG trade plan requires "
                        "stop < entry < target."
                    )
                )

        elif self.side == TradeBias.SHORT:

            if not (
                self.take_profit
                <
                self.entry_price
                <
                self.stop_loss
            ):

                raise ValueError(
                    (
                        "SHORT trade plan requires "
                        "target < entry < stop."
                    )
                )

        else:

            raise ValueError(
                (
                    "TradePlan.side must "
                    "be LONG or SHORT."
                )
            )

        return self


@dataclass(slots=True)
class TradePlanConfig:
    """
    CHARTS Trade Plan V1.

    4H + 1H:
        決定主要方向。

    15m:
        決定目前是否可以建立進場計畫。

    Stop:
        15m structure + ATR buffer。

    Target:
        優先使用 1H / 4H 下一個
        support/resistance。

        如果前方沒有明確 level，
        才使用 minimum R:R target。
    """

    entry_timeframe: str = "15m"

    anchor_timeframes: tuple[
        str,
        str,
    ] = (
        "4H",
        "1H",
    )

    minimum_risk_reward: float = 2.0

    atr_stop_multiplier: float = 1.20

    structure_atr_buffer: float = 0.25

    maximum_structure_distance_atr: float = 3.0

    minimum_confidence: float = 0.45


class TradePlanBuilder:
    """
    Deterministic CHARTS trade-plan builder.

    這不是第七個 Agent。

    它屬於 CHARTS 的責任：

        Direction
        Entry
        Stop
        Target
        Invalidation

    RISK 仍負責：

        size
        exposure
        max loss
        account risk

    DECISION 仍負責：

        LONG / SHORT / WAIT
    """

    def __init__(
        self,
        config: TradePlanConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else TradePlanConfig()
        )

    def build(
        self,
        charts: ChartsOutput,
    ) -> TradePlan | None:

        if (
            charts.status
            !=
            AgentStatus.SUCCESS
        ):

            return None

        analyses = (
            charts.timeframe_analyses
        )

        first_tf, second_tf = (
            self.config
            .anchor_timeframes
        )

        first = analyses.get(
            first_tf
        )

        second = analyses.get(
            second_tf
        )

        entry_tf = analyses.get(
            self.config
            .entry_timeframe
        )

        if (
            first is None
            or
            second is None
            or
            entry_tf is None
        ):

            return None

        side = (
            self._resolve_side(
                first,
                second,
            )
        )

        if side is None:

            return None

        # 15m 必須已經重新回到大方向。
        # 如果大方向空、15m 還在多頭反彈，
        # 現在不建立可執行 Trade Plan。

        if (
            entry_tf.bias
            !=
            side
        ):

            return None

        if (
            charts.confidence
            <
            self.config.minimum_confidence
        ):

            return None

        entry = (
            self._latest_close(
                entry_tf
            )
        )

        if (
            entry is None
            or
            entry <= 0
        ):

            return None

        atr = (
            self._atr(
                entry_tf
            )
        )

        if (
            atr is None
            or
            atr <= 0
        ):

            atr_pct = (
                self._atr_pct(
                    entry_tf
                )
            )

            if (
                atr_pct is not None
                and
                atr_pct > 0
            ):

                atr = (
                    entry
                    *
                    atr_pct
                    /
                    100.0
                )

        # 最後 fallback。
        # 只用於沒有 ATR 的異常資料狀況。

        if (
            atr is None
            or
            atr <= 0
        ):

            atr = (
                entry
                *
                0.0075
            )

        entry_levels = (
            self._levels(
                entry_tf
            )
        )

        support = (
            self._positive_float(
                entry_levels.get(
                    "support"
                )
            )
        )

        resistance = (
            self._positive_float(
                entry_levels.get(
                    "resistance"
                )
            )
        )

        stop = (
            self._build_stop(
                side=side,
                entry=entry,
                atr=atr,
                support=support,
                resistance=resistance,
            )
        )

        if (
            stop is None
            or
            stop <= 0
        ):

            return None

        risk_distance = abs(
            entry
            -
            stop
        )

        if risk_distance <= 0:

            return None

        target = (
            self._build_target(
                side=side,
                entry=entry,
                risk_distance=(
                    risk_distance
                ),
                analyses=analyses,
            )
        )

        if target is None:

            return None

        reward_distance = abs(
            target
            -
            entry
        )

        rr = (
            reward_distance
            /
            risk_distance
        )

        if (
            rr
            <
            self.config
            .minimum_risk_reward
        ):

            return None

        risk_pct = (
            risk_distance
            /
            entry
            *
            100.0
        )

        reward_pct = (
            reward_distance
            /
            entry
            *
            100.0
        )

        confidence = (
            self._confidence(
                charts=charts,
                first=first,
                second=second,
                entry_tf=entry_tf,
            )
        )

        reasons = [
            (
                f"{first_tf} and "
                f"{second_tf} aligned "
                f"{side.value.upper()}."
            ),
            (
                f"{self.config.entry_timeframe} "
                f"confirmed "
                f"{side.value.upper()}."
            ),
            (
                "Stop is derived from "
                "15m structure and ATR."
            ),
            (
                "Target respects higher-timeframe "
                "support/resistance and minimum "
                f"R:R {self.config.minimum_risk_reward:.2f}."
            ),
        ]

        return TradePlan(
            symbol=(
                charts.symbol
                .strip()
                .upper()
            ),

            side=side,

            setup_type=(
                "htf_trend_15m_confirmation"
            ),

            entry_timeframe=(
                self.config
                .entry_timeframe
            ),

            anchor_timeframes=[
                first_tf,
                second_tf,
            ],

            entry_price=entry,

            stop_loss=stop,

            take_profit=target,

            invalidation_price=stop,

            risk_distance_pct=(
                risk_pct
            ),

            reward_distance_pct=(
                reward_pct
            ),

            risk_reward_ratio=rr,

            confidence=confidence,

            atr=atr,

            support=support,

            resistance=resistance,

            reasons=reasons,
        )

    def _resolve_side(
        self,
        first: TimeframeAnalysis,
        second: TimeframeAnalysis,
    ) -> TradeBias | None:

        directional = (
            TradeBias.LONG,
            TradeBias.SHORT,
        )

        if (
            first.bias
            not in directional
            or
            second.bias
            not in directional
        ):

            return None

        if (
            first.bias
            !=
            second.bias
        ):

            return None

        return first.bias

    def _build_stop(
        self,
        *,
        side: TradeBias,
        entry: float,
        atr: float,
        support: float | None,
        resistance: float | None,
    ) -> float | None:

        atr_stop_distance = (
            atr
            *
            self.config
            .atr_stop_multiplier
        )

        buffer = (
            atr
            *
            self.config
            .structure_atr_buffer
        )

        if side == TradeBias.LONG:

            atr_stop = (
                entry
                -
                atr_stop_distance
            )

            if (
                support is not None
                and
                support < entry
            ):

                structure_distance = (
                    entry
                    -
                    support
                )

                if (
                    structure_distance
                    <=
                    atr
                    *
                    self.config
                    .maximum_structure_distance_atr
                ):

                    structure_stop = (
                        support
                        -
                        buffer
                    )

                    return min(
                        atr_stop,
                        structure_stop,
                    )

            return atr_stop

        if side == TradeBias.SHORT:

            atr_stop = (
                entry
                +
                atr_stop_distance
            )

            if (
                resistance is not None
                and
                resistance > entry
            ):

                structure_distance = (
                    resistance
                    -
                    entry
                )

                if (
                    structure_distance
                    <=
                    atr
                    *
                    self.config
                    .maximum_structure_distance_atr
                ):

                    structure_stop = (
                        resistance
                        +
                        buffer
                    )

                    return max(
                        atr_stop,
                        structure_stop,
                    )

            return atr_stop

        return None

    def _build_target(
        self,
        *,
        side: TradeBias,
        entry: float,
        risk_distance: float,
        analyses: dict[
            str,
            TimeframeAnalysis,
        ],
    ) -> float | None:

        target_levels: list[
            float
        ] = []

        for timeframe in (
            "1H",
            "4H",
        ):

            analysis = (
                analyses.get(
                    timeframe
                )
            )

            if analysis is None:

                continue

            levels = (
                self._levels(
                    analysis
                )
            )

            if side == TradeBias.LONG:

                level = (
                    self._positive_float(
                        levels.get(
                            "resistance"
                        )
                    )
                )

                if (
                    level is not None
                    and
                    level > entry
                ):

                    target_levels.append(
                        level
                    )

            else:

                level = (
                    self._positive_float(
                        levels.get(
                            "support"
                        )
                    )
                )

                if (
                    level is not None
                    and
                    level < entry
                ):

                    target_levels.append(
                        level
                    )

        minimum_reward = (
            risk_distance
            *
            self.config
            .minimum_risk_reward
        )

        if side == TradeBias.LONG:

            minimum_target = (
                entry
                +
                minimum_reward
            )

            if target_levels:

                nearest = min(
                    target_levels
                )

                # 前方 resistance 太近，
                # 不准把 target 硬畫到 resistance 後面。

                if (
                    nearest
                    <
                    minimum_target
                ):

                    return None

                return nearest

            return minimum_target

        if side == TradeBias.SHORT:

            minimum_target = (
                entry
                -
                minimum_reward
            )

            if minimum_target <= 0:

                return None

            if target_levels:

                nearest = max(
                    target_levels
                )

                # 前方 support 太近，
                # 不建立低 R:R 的交易。

                if (
                    nearest
                    >
                    minimum_target
                ):

                    return None

                return nearest

            return minimum_target

        return None

    @staticmethod
    def _latest_close(
        analysis: TimeframeAnalysis,
    ) -> float | None:

        return (
            TradePlanBuilder
            ._positive_float(
                analysis
                .indicators
                .get(
                    "latest_close"
                )
            )
        )

    @staticmethod
    def _atr(
        analysis: TimeframeAnalysis,
    ) -> float | None:

        atr = (
            analysis
            .indicators
            .get(
                "atr",
                {},
            )
        )

        if not isinstance(
            atr,
            dict,
        ):

            return None

        return (
            TradePlanBuilder
            ._positive_float(
                atr.get(
                    "value"
                )
            )
        )

    @staticmethod
    def _atr_pct(
        analysis: TimeframeAnalysis,
    ) -> float | None:

        atr = (
            analysis
            .indicators
            .get(
                "atr",
                {},
            )
        )

        if not isinstance(
            atr,
            dict,
        ):

            return None

        return (
            TradePlanBuilder
            ._positive_float(
                atr.get(
                    "percent"
                )
            )
        )

    @staticmethod
    def _levels(
        analysis: TimeframeAnalysis,
    ) -> dict:

        structure = (
            analysis
            .market_structure
            or {}
        )

        levels = (
            structure.get(
                "support_resistance",
                {},
            )
        )

        if not isinstance(
            levels,
            dict,
        ):

            return {}

        return levels

    @staticmethod
    def _confidence(
        *,
        charts: ChartsOutput,
        first: TimeframeAnalysis,
        second: TimeframeAnalysis,
        entry_tf: TimeframeAnalysis,
    ) -> float:

        value = (
            charts.confidence
            *
            0.35
            +
            first.confidence
            *
            0.25
            +
            second.confidence
            *
            0.25
            +
            entry_tf.confidence
            *
            0.15
        )

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )

    @staticmethod
    def _positive_float(
        value,
    ) -> float | None:

        try:

            result = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if result <= 0:

            return None

        if result != result:

            return None

        return result
