from __future__ import annotations

import math

from dataclasses import (
    dataclass,
)

from statistics import (
    pstdev,
)

from typing import (
    Any,
    Sequence,
)

from .models import (
    CandleData,
)


@dataclass(slots=True)
class TechnicalIndicatorsConfig:
    """
    CHARTS deterministic indicator 設定。

    預設：

        EMA:
            20
            50
            200

        RSI:
            14

        MACD:
            12 / 26 / 9

        ATR:
            14

        Bollinger:
            20 / 2

        Volume SMA:
            20
    """

    ema_periods: tuple[
        int,
        ...,
    ] = (
        20,
        50,
        200,
    )

    rsi_period: int = 14

    macd_fast_period: int = 12

    macd_slow_period: int = 26

    macd_signal_period: int = 9

    atr_period: int = 14

    bollinger_period: int = 20

    bollinger_stddev: float = 2.0

    volume_sma_period: int = 20

    def __post_init__(
        self,
    ) -> None:

        if not self.ema_periods:

            raise ValueError(
                "ema_periods cannot be empty."
            )

        for period in self.ema_periods:

            if period <= 0:

                raise ValueError(
                    "EMA periods must "
                    "be greater than 0."
                )

        if self.rsi_period <= 0:

            raise ValueError(
                "rsi_period must "
                "be greater than 0."
            )

        if (
            self.macd_fast_period
            <= 0
        ):

            raise ValueError(
                "macd_fast_period must "
                "be greater than 0."
            )

        if (
            self.macd_slow_period
            <= 0
        ):

            raise ValueError(
                "macd_slow_period must "
                "be greater than 0."
            )

        if (
            self.macd_signal_period
            <= 0
        ):

            raise ValueError(
                "macd_signal_period must "
                "be greater than 0."
            )

        if (
            self.macd_fast_period
            >=
            self.macd_slow_period
        ):

            raise ValueError(
                "MACD fast period must "
                "be smaller than "
                "slow period."
            )

        if self.atr_period <= 0:

            raise ValueError(
                "atr_period must "
                "be greater than 0."
            )

        if (
            self.bollinger_period
            <= 0
        ):

            raise ValueError(
                "bollinger_period must "
                "be greater than 0."
            )

        if (
            self.bollinger_stddev
            <= 0
        ):

            raise ValueError(
                "bollinger_stddev must "
                "be greater than 0."
            )

        if (
            self.volume_sma_period
            <= 0
        ):

            raise ValueError(
                "volume_sma_period must "
                "be greater than 0."
            )


class TechnicalIndicators:
    """
    純 Python technical indicators。

    不依賴：

        pandas
        numpy
        TA-Lib
        pandas-ta

    所以：

        - production dependency 少
        - backtest 可直接重用
        - unit test 容易
        - 不綁定交易所

    輸入：

        list[CandleData]

    輸出：

        normalized indicator dictionary
    """

    def __init__(
        self,
        config: (
            TechnicalIndicatorsConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else (
                TechnicalIndicatorsConfig()
            )
        )

    def calculate(
        self,
        candles: Sequence[
            CandleData
        ],
    ) -> dict[
        str,
        Any,
    ]:
        """
        計算完整 indicator snapshot。

        candles 會先依 timestamp 排序。

        不足資料的 indicator：

            latest value = None

        不因單一 indicator
        資料不足而丟 exception。
        """

        normalized = (
            self._normalize_candles(
                candles
            )
        )

        if not normalized:

            return (
                self._empty_result()
            )

        closes = [
            candle.close
            for candle
            in normalized
        ]

        highs = [
            candle.high
            for candle
            in normalized
        ]

        lows = [
            candle.low
            for candle
            in normalized
        ]

        volumes = [
            candle.volume
            for candle
            in normalized
        ]

        ema_result = (
            self._calculate_emas(
                closes
            )
        )

        rsi_series = (
            self.rsi(
                closes,
                self.config
                .rsi_period,
            )
        )

        macd_result = (
            self.macd(
                closes,
                fast_period=(
                    self.config
                    .macd_fast_period
                ),
                slow_period=(
                    self.config
                    .macd_slow_period
                ),
                signal_period=(
                    self.config
                    .macd_signal_period
                ),
            )
        )

        atr_series = (
            self.atr(
                normalized,
                self.config
                .atr_period,
            )
        )

        bollinger_result = (
            self.bollinger_bands(
                closes,
                period=(
                    self.config
                    .bollinger_period
                ),
                stddev_multiplier=(
                    self.config
                    .bollinger_stddev
                ),
            )
        )

        volume_sma_series = (
            self.sma(
                volumes,
                self.config
                .volume_sma_period,
            )
        )

        latest_close = (
            closes[-1]
        )

        latest_volume = (
            volumes[-1]
        )

        latest_rsi = (
            self.last_valid(
                rsi_series
            )
        )

        latest_atr = (
            self.last_valid(
                atr_series
            )
        )

        latest_volume_sma = (
            self.last_valid(
                volume_sma_series
            )
        )

        atr_pct = None

        if (
            latest_atr is not None
            and latest_close > 0
        ):

            atr_pct = (
                latest_atr
                /
                latest_close
                *
                100.0
            )

        volume_ratio = None

        if (
            latest_volume_sma
            is not None
            and latest_volume_sma > 0
        ):

            volume_ratio = (
                latest_volume
                /
                latest_volume_sma
            )

        price_change_pct = (
            self._change_pct(
                closes[-2],
                closes[-1],
            )
            if len(closes) >= 2
            else None
        )

        change_5_pct = (
            self._period_change_pct(
                closes,
                5,
            )
        )

        change_20_pct = (
            self._period_change_pct(
                closes,
                20,
            )
        )

        result = {
            "candle_count":
                len(
                    normalized
                ),

            "latest_timestamp":
                normalized[-1]
                .timestamp
                .isoformat(),

            "latest_close":
                latest_close,

            "price_change_pct":
                price_change_pct,

            "change_5_pct":
                change_5_pct,

            "change_20_pct":
                change_20_pct,

            "ema":
                ema_result,

            "rsi": {
                "period":
                    self.config
                    .rsi_period,

                "value":
                    latest_rsi,

                "series":
                    rsi_series,
            },

            "macd":
                macd_result,

            "atr": {
                "period":
                    self.config
                    .atr_period,

                "value":
                    latest_atr,

                "percent":
                    atr_pct,

                "series":
                    atr_series,
            },

            "bollinger":
                bollinger_result,

            "volume": {
                "current":
                    latest_volume,

                "sma_period":
                    self.config
                    .volume_sma_period,

                "sma":
                    latest_volume_sma,

                "ratio":
                    volume_ratio,

                "sma_series":
                    volume_sma_series,
            },

            "data_quality": (
                self._calculate_data_quality(
                    candle_count=len(
                        normalized
                    )
                )
            ),
        }

        return result

    # =================================
    # SMA
    # =================================

    @staticmethod
    def sma(
        values: Sequence[
            float
        ],
        period: int,
    ) -> list[
        float
        | None
    ]:
        """
        Simple Moving Average。

        前 period - 1 個位置
        回傳 None。
        """

        TechnicalIndicators
        ._validate_period(
            period
        )

        values = [
            float(value)
            for value
            in values
        ]

        result: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        if (
            len(values)
            <
            period
        ):

            return result

        rolling_sum = sum(
            values[
                :period
            ]
        )

        result[
            period - 1
        ] = (
            rolling_sum
            /
            period
        )

        for index in range(
            period,
            len(values),
        ):

            rolling_sum += (
                values[index]
                -
                values[
                    index
                    -
                    period
                ]
            )

            result[index] = (
                rolling_sum
                /
                period
            )

        return result

    # =================================
    # EMA
    # =================================

    @staticmethod
    def ema(
        values: Sequence[
            float
        ],
        period: int,
    ) -> list[
        float
        | None
    ]:
        """
        Exponential Moving Average。

        初始 EMA 使用：

            first SMA(period)

        後續：

            EMA =
                price * multiplier
                +
                previous_ema
                * (1 - multiplier)
        """

        TechnicalIndicators
        ._validate_period(
            period
        )

        values = [
            float(value)
            for value
            in values
        ]

        result: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        if (
            len(values)
            <
            period
        ):

            return result

        seed = (
            sum(
                values[
                    :period
                ]
            )
            /
            period
        )

        seed_index = (
            period - 1
        )

        result[
            seed_index
        ] = seed

        multiplier = (
            2.0
            /
            (
                period
                +
                1.0
            )
        )

        previous_ema = (
            seed
        )

        for index in range(
            period,
            len(values),
        ):

            current = (
                values[index]
                *
                multiplier
                +
                previous_ema
                *
                (
                    1.0
                    -
                    multiplier
                )
            )

            result[index] = (
                current
            )

            previous_ema = (
                current
            )

        return result

    # =================================
    # RSI
    # =================================

    @staticmethod
    def rsi(
        values: Sequence[
            float
        ],
        period: int = 14,
    ) -> list[
        float
        | None
    ]:
        """
        Wilder RSI。

        RSI：

            RS =
                avg_gain
                /
                avg_loss

            RSI =
                100
                -
                100 / (1 + RS)
        """

        TechnicalIndicators
        ._validate_period(
            period
        )

        values = [
            float(value)
            for value
            in values
        ]

        result: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        if (
            len(values)
            <=
            period
        ):

            return result

        gains: list[
            float
        ] = []

        losses: list[
            float
        ] = []

        for index in range(
            1,
            period + 1,
        ):

            change = (
                values[index]
                -
                values[
                    index - 1
                ]
            )

            gains.append(
                max(
                    change,
                    0.0,
                )
            )

            losses.append(
                max(
                    -change,
                    0.0,
                )
            )

        avg_gain = (
            sum(gains)
            /
            period
        )

        avg_loss = (
            sum(losses)
            /
            period
        )

        result[
            period
        ] = (
            TechnicalIndicators
            ._rsi_from_averages(
                avg_gain,
                avg_loss,
            )
        )

        for index in range(
            period + 1,
            len(values),
        ):

            change = (
                values[index]
                -
                values[
                    index - 1
                ]
            )

            gain = max(
                change,
                0.0,
            )

            loss = max(
                -change,
                0.0,
            )

            avg_gain = (
                (
                    avg_gain
                    *
                    (
                        period
                        -
                        1
                    )
                )
                +
                gain
            ) / period

            avg_loss = (
                (
                    avg_loss
                    *
                    (
                        period
                        -
                        1
                    )
                )
                +
                loss
            ) / period

            result[index] = (
                TechnicalIndicators
                ._rsi_from_averages(
                    avg_gain,
                    avg_loss,
                )
            )

        return result

    # =================================
    # MACD
    # =================================

    @classmethod
    def macd(
        cls,
        values: Sequence[
            float
        ],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> dict[
        str,
        Any,
    ]:
        """
        MACD。

        line：

            EMA(fast)
            -
            EMA(slow)

        signal：

            EMA(
                MACD line,
                signal_period
            )

        histogram：

            MACD
            -
            signal
        """

        cls._validate_period(
            fast_period
        )

        cls._validate_period(
            slow_period
        )

        cls._validate_period(
            signal_period
        )

        if (
            fast_period
            >=
            slow_period
        ):

            raise ValueError(
                "MACD fast period must "
                "be smaller than "
                "slow period."
            )

        values = [
            float(value)
            for value
            in values
        ]

        fast_ema = cls.ema(
            values,
            fast_period,
        )

        slow_ema = cls.ema(
            values,
            slow_period,
        )

        macd_line: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        for index in range(
            len(values)
        ):

            fast = (
                fast_ema[index]
            )

            slow = (
                slow_ema[index]
            )

            if (
                fast is None
                or slow is None
            ):

                continue

            macd_line[index] = (
                fast
                -
                slow
            )

        signal_line = (
            cls._ema_optional_series(
                macd_line,
                signal_period,
            )
        )

        histogram: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        for index in range(
            len(values)
        ):

            line = (
                macd_line[index]
            )

            signal = (
                signal_line[index]
            )

            if (
                line is None
                or signal is None
            ):

                continue

            histogram[index] = (
                line
                -
                signal
            )

        return {
            "fast_period":
                fast_period,

            "slow_period":
                slow_period,

            "signal_period":
                signal_period,

            "value":
                cls.last_valid(
                    macd_line
                ),

            "signal":
                cls.last_valid(
                    signal_line
                ),

            "histogram":
                cls.last_valid(
                    histogram
                ),

            "line_series":
                macd_line,

            "signal_series":
                signal_line,

            "histogram_series":
                histogram,
        }

    # =================================
    # True Range / ATR
    # =================================

    @staticmethod
    def true_range(
        candles: Sequence[
            CandleData
        ],
    ) -> list[
        float
    ]:
        """
        True Range：

        max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        """

        candles = (
            TechnicalIndicators
            ._normalize_candles(
                candles
            )
        )

        if not candles:

            return []

        result: list[
            float
        ] = []

        for index, candle in enumerate(
            candles
        ):

            high = float(
                candle.high
            )

            low = float(
                candle.low
            )

            if index == 0:

                result.append(
                    high
                    -
                    low
                )

                continue

            previous_close = float(
                candles[
                    index - 1
                ].close
            )

            result.append(
                max(
                    high
                    -
                    low,

                    abs(
                        high
                        -
                        previous_close
                    ),

                    abs(
                        low
                        -
                        previous_close
                    ),
                )
            )

        return result

    @classmethod
    def atr(
        cls,
        candles: Sequence[
            CandleData
        ],
        period: int = 14,
    ) -> list[
        float
        | None
    ]:
        """
        Wilder ATR。

        第一個 ATR：

            SMA(TR, period)

        後續：

            ATR =
                (
                    previous_ATR
                    * (period - 1)
                    +
                    current_TR
                )
                /
                period
        """

        cls._validate_period(
            period
        )

        candles = (
            cls._normalize_candles(
                candles
            )
        )

        result: list[
            float
            | None
        ] = [
            None
        ] * len(
            candles
        )

        if (
            len(candles)
            <
            period
        ):

            return result

        tr = cls.true_range(
            candles
        )

        initial_atr = (
            sum(
                tr[
                    :period
                ]
            )
            /
            period
        )

        result[
            period - 1
        ] = (
            initial_atr
        )

        previous_atr = (
            initial_atr
        )

        for index in range(
            period,
            len(tr),
        ):

            current_atr = (
                (
                    previous_atr
                    *
                    (
                        period
                        -
                        1
                    )
                )
                +
                tr[index]
            ) / period

            result[index] = (
                current_atr
            )

            previous_atr = (
                current_atr
            )

        return result

    # =================================
    # Bollinger Bands
    # =================================

    @classmethod
    def bollinger_bands(
        cls,
        values: Sequence[
            float
        ],
        period: int = 20,
        stddev_multiplier: float = 2.0,
    ) -> dict[
        str,
        Any,
    ]:
        """
        Bollinger Bands。

        middle：

            SMA(period)

        upper：

            SMA
            +
            stddev * multiplier

        lower：

            SMA
            -
            stddev * multiplier
        """

        cls._validate_period(
            period
        )

        if (
            stddev_multiplier
            <= 0
        ):

            raise ValueError(
                "stddev_multiplier must "
                "be greater than 0."
            )

        values = [
            float(value)
            for value
            in values
        ]

        middle = cls.sma(
            values,
            period,
        )

        upper: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        lower: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        bandwidth: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        percent_b: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        for index in range(
            period - 1,
            len(values),
        ):

            window = (
                values[
                    index
                    -
                    period
                    +
                    1:
                    index
                    +
                    1
                ]
            )

            middle_value = (
                middle[index]
            )

            if (
                middle_value
                is None
            ):

                continue

            deviation = (
                pstdev(
                    window
                )
            )

            upper_value = (
                middle_value
                +
                deviation
                *
                stddev_multiplier
            )

            lower_value = (
                middle_value
                -
                deviation
                *
                stddev_multiplier
            )

            upper[index] = (
                upper_value
            )

            lower[index] = (
                lower_value
            )

            if (
                middle_value
                != 0
            ):

                bandwidth[index] = (
                    (
                        upper_value
                        -
                        lower_value
                    )
                    /
                    middle_value
                    *
                    100.0
                )

            band_range = (
                upper_value
                -
                lower_value
            )

            if band_range != 0:

                percent_b[index] = (
                    (
                        values[index]
                        -
                        lower_value
                    )
                    /
                    band_range
                )

        return {
            "period":
                period,

            "stddev_multiplier":
                stddev_multiplier,

            "middle":
                cls.last_valid(
                    middle
                ),

            "upper":
                cls.last_valid(
                    upper
                ),

            "lower":
                cls.last_valid(
                    lower
                ),

            "bandwidth_pct":
                cls.last_valid(
                    bandwidth
                ),

            "percent_b":
                cls.last_valid(
                    percent_b
                ),

            "middle_series":
                middle,

            "upper_series":
                upper,

            "lower_series":
                lower,

            "bandwidth_series":
                bandwidth,

            "percent_b_series":
                percent_b,
        }

    # =================================
    # EMA bundle
    # =================================

    def _calculate_emas(
        self,
        closes: Sequence[
            float
        ],
    ) -> dict[
        str,
        Any,
    ]:

        result: dict[
            str,
            Any,
        ] = {}

        for period in (
            self.config
            .ema_periods
        ):

            series = (
                self.ema(
                    closes,
                    period,
                )
            )

            result[
                str(period)
            ] = {
                "period":
                    period,

                "value":
                    self.last_valid(
                        series
                    ),

                "series":
                    series,
            }

        return result

    # =================================
    # Data quality
    # =================================

    def _calculate_data_quality(
        self,
        candle_count: int,
    ) -> float:
        """
        Indicator 計算所需資料完整度。

        最大需求通常是：

            EMA 200

        或其他設定中的
        longest lookback。

        額外給 MACD signal
        留出 warm-up。
        """

        required = max(
            max(
                self.config
                .ema_periods
            ),

            self.config
            .rsi_period
            +
            1,

            (
                self.config
                .macd_slow_period
                +
                self.config
                .macd_signal_period
            ),

            self.config
            .atr_period,

            self.config
            .bollinger_period,

            self.config
            .volume_sma_period,
        )

        if required <= 0:

            return 0.0

        return (
            self._clamp01(
                candle_count
                /
                required
            )
        )

    # =================================
    # Optional-series EMA
    # =================================

    @classmethod
    def _ema_optional_series(
        cls,
        values: Sequence[
            float
            | None
        ],
        period: int,
    ) -> list[
        float
        | None
    ]:
        """
        對包含 None 的 aligned series
        計算 EMA。

        用於：

            MACD signal line。

        保留原始 index alignment。
        """

        cls._validate_period(
            period
        )

        output: list[
            float
            | None
        ] = [
            None
        ] * len(
            values
        )

        valid_positions: list[
            int
        ] = []

        valid_values: list[
            float
        ] = []

        for index, value in enumerate(
            values
        ):

            if value is None:

                continue

            valid_positions.append(
                index
            )

            valid_values.append(
                float(
                    value
                )
            )

        if (
            len(valid_values)
            <
            period
        ):

            return output

        compact_ema = cls.ema(
            valid_values,
            period,
        )

        for compact_index, value in enumerate(
            compact_ema
        ):

            if value is None:

                continue

            original_index = (
                valid_positions[
                    compact_index
                ]
            )

            output[
                original_index
            ] = value

        return output

    # =================================
    # Helpers
    # =================================

    @staticmethod
    def last_valid(
        values: Sequence[
            float
            | None
        ],
    ) -> float | None:
        """
        找到最後一個有效 numeric value。
        """

        for value in reversed(
            values
        ):

            if value is None:

                continue

            value = float(
                value
            )

            if math.isfinite(
                value
            ):

                return value

        return None

    @staticmethod
    def _normalize_candles(
        candles: Sequence[
            CandleData
        ],
    ) -> list[
        CandleData
    ]:
        """
        統一 timestamp 順序。

        oldest
            ↓
        newest
        """

        return sorted(
            list(
                candles
            ),
            key=lambda candle:
                candle.timestamp,
        )

    @staticmethod
    def _validate_period(
        period: int,
    ) -> None:

        if (
            not isinstance(
                period,
                int,
            )
            or period <= 0
        ):

            raise ValueError(
                "Indicator period must "
                "be a positive integer."
            )

    @staticmethod
    def _rsi_from_averages(
        avg_gain: float,
        avg_loss: float,
    ) -> float:

        if (
            avg_loss == 0
            and avg_gain == 0
        ):

            return 50.0

        if avg_loss == 0:

            return 100.0

        if avg_gain == 0:

            return 0.0

        relative_strength = (
            avg_gain
            /
            avg_loss
        )

        return (
            100.0
            -
            (
                100.0
                /
                (
                    1.0
                    +
                    relative_strength
                )
            )
        )

    @staticmethod
    def _change_pct(
        previous: float,
        current: float,
    ) -> float | None:

        previous = float(
            previous
        )

        current = float(
            current
        )

        if previous == 0:

            return None

        return (
            (
                current
                -
                previous
            )
            /
            previous
            *
            100.0
        )

    @classmethod
    def _period_change_pct(
        cls,
        values: Sequence[
            float
        ],
        periods: int,
    ) -> float | None:
        """
        periods=5：

        最新 close
        相對 5 根 K 前 close
        的變化百分比。
        """

        if periods <= 0:

            return None

        if (
            len(values)
            <=
            periods
        ):

            return None

        previous = (
            values[
                -periods
                -
                1
            ]
        )

        current = (
            values[-1]
        )

        return cls._change_pct(
            previous,
            current,
        )

    @staticmethod
    def _clamp01(
        value: float,
    ) -> float:

        return max(
            0.0,
            min(
                1.0,
                float(
                    value
                ),
            ),
        )

    @staticmethod
    def _empty_result(
    ) -> dict[
        str,
        Any,
    ]:

        return {
            "candle_count":
                0,

            "latest_timestamp":
                None,

            "latest_close":
                None,

            "price_change_pct":
                None,

            "change_5_pct":
                None,

            "change_20_pct":
                None,

            "ema":
                {},

            "rsi": {
                "period":
                    None,

                "value":
                    None,

                "series":
                    [],
            },

            "macd": {
                "value":
                    None,

                "signal":
                    None,

                "histogram":
                    None,

                "line_series":
                    [],

                "signal_series":
                    [],

                "histogram_series":
                    [],
            },

            "atr": {
                "period":
                    None,

                "value":
                    None,

                "percent":
                    None,

                "series":
                    [],
            },

            "bollinger": {
                "middle":
                    None,

                "upper":
                    None,

                "lower":
                    None,

                "bandwidth_pct":
                    None,

                "percent_b":
                    None,

                "middle_series":
                    [],

                "upper_series":
                    [],

                "lower_series":
                    [],

                "bandwidth_series":
                    [],

                "percent_b_series":
                    [],
            },

            "volume": {
                "current":
                    None,

                "sma":
                    None,

                "ratio":
                    None,

                "sma_series":
                    [],
            },

            "data_quality":
                0.0,
        }
