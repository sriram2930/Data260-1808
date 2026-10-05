"""
Part-7/envelope.py -- DATA-260 HW5, Part 2.B

The single {ok, data, error} response shape used by all three domain tools
(domain_server.py), and reused unchanged for execute_tool in Part 4, per the
assignment ("define it once here and carry it through").
"""

from __future__ import annotations

from typing import Any


def ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None}


def fail(error: str) -> dict:
    return {"ok": False, "data": None, "error": error}
