from __future__ import annotations

from enum import StrEnum


OKX_REST_BASE_URL = "https://openapi.okx.com"


class InstrumentType(StrEnum):
    SPOT = "SPOT"
    MARGIN = "MARGIN"
    SWAP = "SWAP"
    FUTURES = "FUTURES"
    OPTION = "OPTION"


class Bar(StrEnum):
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"

    H1 = "1H"
    H2 = "2H"
    H4 = "4H"

    H6_UTC = "6Hutc"
    H12_UTC = "12Hutc"

    D1_UTC = "1Dutc"
    D2_UTC = "2Dutc"
    D3_UTC = "3Dutc"

    W1_UTC = "1Wutc"
    MN1_UTC = "1Mutc"
    MN3_UTC = "3Mutc"
