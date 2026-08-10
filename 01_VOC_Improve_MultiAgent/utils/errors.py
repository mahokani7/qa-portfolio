"""MCP와 Web 계층에서 사용하는 일관된 결과 형식."""

from __future__ import annotations

from typing import Any


def success_result(**payload: Any) -> dict[str, Any]:
    return {"ok": True, "error_code": None, "message": "success", **payload}


def error_result(
    error_code: str,
    message: str,
    *,
    trace: str = "",
    **details: Any,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
        "trace": trace,
        **details,
    }
