# bot/gas_client.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv, find_dotenv

# Подтягиваем .env
load_dotenv(find_dotenv())

GAS_URL = os.getenv("GAS_URL")
GAS_SECRET = os.getenv("GAS_SECRET")


class GasError(RuntimeError):
    pass


def _assert_env() -> None:
    if not GAS_URL or not GAS_SECRET:
        raise GasError("GAS_URL / GAS_SECRET не заданы (проверь .env)")


async def gas_call(
    intent: str,
    args: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Универсальный вызов GAS: передаём intent и args.
    follow_redirects=True — чтобы автоматически ходить по 302 с Apps Script.
    verify=False/trust_env=True — чтобы не падать на корпоративном MITM-прокси/сертификате.
    """
    _assert_env()

    payload = {
        "key": GAS_SECRET,
        "intent": intent,
        "args": args or {},
        "user": user or {},
    }

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        verify=False,
        trust_env=True,
    ) as cli:
        r = await cli.post(GAS_URL, json=payload)
        r.raise_for_status()
        return r.json()

async def list_managers() -> dict:
    return await gas_call("list_managers", {})


async def list_projects_by_status(unit: str | None = None) -> dict:
    payload = {"unit": unit} if unit else {}
    return await gas_call("list_projects_by_status", payload)


async def list_projects_by_status(unit: str | None = None) -> dict:
    payload = {"unit": unit} if unit else {}
    return await gas_call("list_projects_by_status", payload)


# ===== Удобные врапперы под конкретные интенты =====

async def load_all(**kwargs) -> Dict[str, Any]:
    """
    kwargs: from="YYYY-MM-DD", to="YYYY-MM-DD" (опционально)
    """
    return await gas_call("get_all_load", kwargs)


async def load_unit(**kwargs) -> Dict[str, Any]:
    """
    kwargs: unit="2.1" (обязательно), from/to (опционально)
    """
    return await gas_call("get_unit_load", kwargs)

async def list_units() -> dict:
    return await gas_call("list_units", {})


# по желанию можно добавить и остальные обёртки:
async def list_units_and_managers() -> Dict[str, Any]:
    return await gas_call("list_units_and_managers")

async def list_projects_for_unit(unit: str) -> Dict[str, Any]:
    return await gas_call("list_projects_for_unit", {"unit": unit})

async def add_project(**kwargs) -> Dict[str, Any]:
    return await gas_call("add_project", kwargs)

async def move_project(**kwargs) -> Dict[str, Any]:
    return await gas_call("move_project", kwargs)

async def extend_deadline(**kwargs) -> Dict[str, Any]:
    return await gas_call("extend_deadline", kwargs)

async def remove_project(**kwargs) -> Dict[str, Any]:
    return await gas_call("remove_project", kwargs)

async def set_manager(**kwargs) -> Dict[str, Any]:
    return await gas_call("set_manager", kwargs)

async def list_units_min() -> dict:
    return await gas_call("list_units_min", {})

async def list_active_projects(unit: str) -> dict:
    return await gas_call("list_active_projects", {"unit": unit})

async def notify_upcoming(days: int = 30) -> dict:
    return await gas_call("notify_upcoming", {"days": days})

async def mark_paused(unit: str, project: str) -> dict:
    return await gas_call("mark_paused", {"unit": unit, "project": project})


async def mark_pending(unit: str, project: str) -> dict:
    return await gas_call("mark_pending", {"unit": unit, "project": project})

# === Завершения проектов ===
async def list_endings_in_month(unit: str, month: int, year: int):
    return await gas_call("list_endings_in_month", {"unit": unit, "month": month, "year": year})

async def list_endings_within_months(unit: str, n: int):
    return await gas_call("list_endings_within_months", {"unit": unit, "months": n})

async def add_project(unit: str, project: str, start: str | None = None, end: str | None = None, manager: str | None = None) -> dict:
    payload: dict = {"unit": unit, "project": project}
    if start:   payload["start"]   = start
    if end:     payload["end"]     = end
    if manager: payload["manager"] = manager
    return await gas_call("add_project", payload)

async def list_units_and_managers() -> dict:
    return await gas_call("list_units_and_managers", {})

async def get_project_info(unit: str, project: str) -> dict:
    return await gas_call("get_project_info", {"unit": unit, "project": project})
