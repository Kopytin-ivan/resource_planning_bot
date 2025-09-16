from __future__ import annotations
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv, find_dotenv

# грузим .env при импорте
load_dotenv(find_dotenv())

GAS_URL = os.getenv("GAS_URL")
GAS_SECRET = os.getenv("GAS_SECRET")


class GasError(RuntimeError):
    pass


def _assert_env():
    if not GAS_URL or not GAS_SECRET:
        raise GasError("GAS_URL / GAS_SECRET не заданы (проверь .env)")


async def gas_call(
    intent: str,
    args: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Единая обёртка вызовов твоего Apps Script."""
    _assert_env()
    payload = {"key": GAS_SECRET, "intent": intent, "args": args or {}, "user": user or {}}

    # ⚠️ DEV-КОСТЫЛЬ: отключаем проверку сертификата (корп. SSL-инспекция)
    async with httpx.AsyncClient(timeout=30, verify=False, trust_env=True) as cli:
        r = await cli.post(GAS_URL, json=payload)
        r.raise_for_status()
        return r.json()


# Шорткаты
async def list_units_and_managers() -> Dict[str, Any]:
    return await gas_call("list_units_and_managers", {})


async def get_all_load(dt_from: Optional[str] = None, dt_to: Optional[str] = None) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    if dt_from:
        args["from"] = dt_from
    if dt_to:
        args["to"] = dt_to
    return await gas_call("get_all_load", args)


async def get_unit_load(unit_code: str, dt_from: Optional[str] = None, dt_to: Optional[str] = None) -> Dict[str, Any]:
    args: Dict[str, Any] = {"unit": unit_code}
    if dt_from:
        args["from"] = dt_from
    if dt_to:
        args["to"] = dt_to
    return await gas_call("get_unit_load", args)
