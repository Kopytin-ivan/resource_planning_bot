# bot/utils/periods.py
from __future__ import annotations
from datetime import date, datetime, timedelta

def iso(d: date) -> str:
    return d.isoformat()

def month_bounds(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end

def quarter_bounds(today: date) -> tuple[date, date]:
    q = (today.month - 1) // 3  # 0..3
    start_month = 1 + q * 3
    start = date(today.year, start_month, 1)
    # конец квартала — последний день третьего месяца
    if start_month + 2 == 12:
        end = date(today.year, 12, 31)
    else:
        next_month = start_month + 3
        end = date(today.year, next_month, 1) - timedelta(days=1)
    return start, end

def year_bounds(today: date) -> tuple[date, date]:
    start = date(today.year, 1, 1)
    end = date(today.year, 12, 31)
    return start, end

def period_bounds(kind: str, today: date | None = None) -> tuple[str, str]:
    """
    kind: 'month' | 'quarter' | 'year' | 'custom:<YYYY-MM-DD>:<YYYY-MM-DD>'
    Возвращает (from_iso, to_iso)
    """
    t = today or date.today()
    if kind == "month":
        s, e = month_bounds(t)
        return iso(s), iso(e)
    if kind == "quarter":
        s, e = quarter_bounds(t)
        return iso(s), iso(e)
    if kind == "year":
        s, e = year_bounds(t)
        return iso(s), iso(e)
    if kind.startswith("custom:"):
        parts = kind.split(":", 2)
        if len(parts) == 3:
            return parts[1], parts[2]
    # по умолчанию — 12 недельное окно «с понедельника» как было раньше
    start = t - timedelta(days=(t.weekday()))         # понедельник этой недели
    end = start + timedelta(days=7*12 - 1)            # 12 недель - 1 день
    return iso(start), iso(end)
