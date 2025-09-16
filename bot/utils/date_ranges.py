from datetime import date
from calendar import monthrange

def month_range(year: int, month: int) -> tuple[str, str]:
    d1 = date(year, month, 1)
    d2 = date(year, month, monthrange(year, month)[1])
    return d1.isoformat(), d2.isoformat()

def preset_range(preset: str) -> tuple[str|None, str|None]:
    today = date.today()
    if preset == "this_month":
        return month_range(today.year, today.month)
    if preset == "next_month":
        m = 1 if today.month == 12 else today.month + 1
        y = today.year + 1 if today.month == 12 else today.year
        return month_range(y, m)
    if preset == "quarter":
        q = (today.month - 1)//3
        months = [q*3+1, q*3+2, q*3+3]
        start = month_range(today.year, months[0])[0]
        end   = month_range(today.year, months[-1])[1]
        return start, end
    if preset == "year":
        return f"{today.year}-01-01", f"{today.year}-12-31"
    return None, None
