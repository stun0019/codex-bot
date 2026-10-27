from __future__ import annotations


class OKXError(Exception):
    """所有 OKX 相關錯誤的基底類別。"""


class OKXRequestError(OKXError):
    """HTTP、網路或連線錯誤。"""


class OKXAPIError(OKXError):
    """OKX API 回傳非成功 code。"""

    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:
        self.code = code
        self.message = message

        super().__init__(
            f"OKX API error {code}: {message}"
        )


class OKXDataError(OKXError):
    """OKX 回傳資料格式異常。"""
