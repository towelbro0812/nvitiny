"""窄屏用的數值格式化：每一個字元都要爭取。"""

from __future__ import annotations

_UNITS = ("B", "K", "M", "G", "T")


def bytes_short(n: int | None, *, precision: int = 1) -> str:
    """10864455680 -> '10.1G'；小數點只在有意義時保留。"""
    if n is None:
        return "-"
    value = float(n)
    unit = 0
    while value >= 1024 and unit < len(_UNITS) - 1:
        value /= 1024
        unit += 1
    if unit == 0:
        return f"{int(value)}{_UNITS[unit]}"
    if value >= 100:
        return f"{value:.0f}{_UNITS[unit]}"
    return f"{value:.{precision}f}{_UNITS[unit]}"


def pct(value: float | None, *, width: int = 3) -> str:
    if value is None:
        return "-".rjust(width) + " "
    return f"{value:.0f}".rjust(width) + "%"


def watts(usage_mw: int | None, limit_mw: int | None, *, compact: bool = False) -> str | None:
    """GB10 沒有 power_limit，所以限制值缺席時只印用量、不硬湊分母。"""
    if usage_mw is None:
        return None
    used = f"{usage_mw / 1000:.0f}W"
    # 極窄時 381W/450W 會吃掉 9 格，只留用量把空間讓給 bar
    if compact or limit_mw is None:
        return used
    return f"{used}/{limit_mw / 1000:.0f}W"


def celsius(value: int | None) -> str | None:
    return None if value is None else f"{value}°C"


def mhz(value: int | None) -> str | None:
    return None if value is None else f"{value}MHz"


def truncate(text: str, width: int, *, ellipsis: str = "…") -> str:
    """以顯示格數截斷（rich 的 cell_len 會處理 CJK 寬字元）。"""
    from rich.cells import cell_len, set_cell_size

    if width <= 0:
        return ""
    if cell_len(text) <= width:
        return text
    if width <= 1:
        return ellipsis[:width]
    return set_cell_size(text, width - 1) + ellipsis


def basename(command: str | None, fallback: str | None) -> str:
    """取執行檔名，路徑一律丟掉 —— 窄屏放不下完整路徑。"""
    if fallback:
        return fallback
    if not command:
        return "?"
    return command.split()[0].rsplit("/", 1)[-1] if command.split() else "?"
