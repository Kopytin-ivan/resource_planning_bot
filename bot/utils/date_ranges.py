# bot/utils/date_ranges.py
from datetime import date, timedelta
from calendar import monthrange

def _fmt(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def _month_bounds(y: int, m: int) -> tuple[date, date]:
    last = monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last)

def _quarter_bounds(d: date) -> tuple[date, date]:
    q = (d.month - 1) // 3  # 0..3
    start_month = q * 3 + 1
    y = d.year
    start = date(y, start_month, 1)
    end_m = start_month + 2
    _, last = monthrange(y, end_m)
    end = date(y, end_m, last)
    return start, end

def _half_year_bounds(d: date) -> tuple[date, date]:
    if d.month <= 6:
        start, end = date(d.year, 1, 1), date(d.year, 6, monthrange(d.year, 6)[1])
    else:
        start, end = date(d.year, 7, 1), date(d.year, 12, 31)
    return start, end

def period_to_range(period: str) -> dict | None:
    """
    Возвращает {"from":"YYYY-MM-DD","to":"YYYY-MM-DD"} для предустановленных периодов.
    "none" -> None (без фильтра по датам).
    """
    period = (period or "").strip().lower()
    today = date.today()

    if period == "none":
        return None

    if period == "this_month":
        start, end = _month_bounds(today.year, today.month)
        return {"from": _fmt(start), "to": _fmt(end)}

    if period == "next_month":
        y, m = (today.year + (1 if today.month == 12 else 0),
                1 if today.month == 12 else today.month + 1)
        start, end = _month_bounds(y, m)
        return {"from": _fmt(start), "to": _fmt(end)}

    if period == "quarter":
        start, end = _quarter_bounds(today)
        return {"from": _fmt(start), "to": _fmt(end)}

    if period == "half_year":
        start, end = _half_year_bounds(today)
        return {"from": _fmt(start), "to": _fmt(end)}

    if period == "year":
        start, end = date(today.year, 1, 1), date(today.year, 12, 31)
        return {"from": _fmt(start), "to": _fmt(end)}

    # неизвестный период — без фильтра
    return None
