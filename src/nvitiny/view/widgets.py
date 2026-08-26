"""可重用的畫面元件。每個函式都拿到明確的寬度預算，不准超出。"""

from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text

from . import units as fmt
from . import theme

BAR_FULL = "█"
BAR_EMPTY = "░"
BAR_LEFT = "▕"
BAR_RIGHT = "▏"


def bar(pct: float | None, width: int, color: str) -> Text:
    """▕████░░░░▏ —— 兩側的細括號各佔 1 格，已計入 width。"""
    if width < 3:
        return Text(" " * max(0, width))
    inner = width - 2
    filled = 0 if pct is None else max(0, min(inner, round(inner * pct / 100)))
    out = Text(BAR_LEFT, style=theme.BAR_EMPTY)
    out.append(BAR_FULL * filled, style=color)
    out.append(BAR_EMPTY * (inner - filled), style=theme.BAR_EMPTY)
    out.append(BAR_RIGHT, style=theme.BAR_EMPTY)
    return out


def justify(left: Text, right: Text, width: int) -> Text:
    """左右各靠一邊，中間補滿。右邊放不下就整個丟掉，絕不換行。"""
    gap = width - cell_len(left.plain) - cell_len(right.plain)
    if gap < 1:
        return left if cell_len(left.plain) <= width else Text(fmt.truncate(left.plain, width))
    out = left.copy()
    out.append(" " * gap)
    out.append(right)
    return out


def metric_row(
    label: str,
    pct: float | None,
    color: str,
    width: int,
    right: str | None = None,
    right_style: str = "",
    right_width: int | None = None,
) -> Text:
    """`U ▕████░░░░▏ 43%  46°C` —— bar 吃掉所有剩餘寬度。

    right_width 是同一組 metric row 共用的右欄寬度。少了它，每列會各自
    用自己的右欄長度去算 bar，導致 46°C 那列的 bar 比 13W 那列短一格。
    """
    right = right or ""
    # 右欄靠右對齊到共用欄寬，兩列的 bar 才會等長、右緣才會切齊
    col = right_width if right_width is not None else cell_len(right)
    if right:
        right = right.rjust(col + len(right) - cell_len(right))
    # label(1) + 空格(1) + 百分比(4) + 右欄前的兩個空格
    fixed = len(label) + 1 + 4 + (2 + col if col else 0)
    bar_width = max(3, width - fixed)
    out = Text()
    out.append(label, style=theme.LABEL)
    out.append(" ")
    out.append_text(bar(pct, bar_width, color))
    out.append(fmt.pct(pct), style=color)
    if right:
        out.append("  ")
        out.append(right, style=right_style or color)
    return out


def rule(width: int) -> Text:
    return Text("─" * max(0, width), style=theme.RULE)


def proc_row(proc, width: int, *, show_user: bool, show_cpu: bool,
             gpu_memory_total: int | None = None) -> Text:
    """process 一行。欄位依寬度預算由右往左砍。"""
    pid = str(proc.pid).rjust(6)
    mem = fmt.bytes_short(proc.gpu_memory).rjust(5)

    out = Text()
    out.append(pid, style=theme.DIM)
    used = 6
    if show_user:
        user = fmt.truncate(proc.username or "-", 6).ljust(6)
        out.append(" ")
        out.append(user, style=theme.LABEL)
        used += 7
    out.append(" ")
    share = (
        100 * proc.gpu_memory / gpu_memory_total
        if proc.gpu_memory and gpu_memory_total
        else None
    )
    out.append(mem, style=theme.mem_color(share))
    used += 6
    if show_cpu and proc.cpu_percent is not None:
        # 多執行緒的 process 會超過 100%，欄寬要留 4 位
        cpu = f"{proc.cpu_percent:.0f}%".rjust(5)
        out.append(" ")
        out.append(cpu, style=theme.load_color(min(proc.cpu_percent, 100)))
        used += 6
    name_width = width - used - 2
    if name_width >= 3:
        out.append("  ")
        out.append(fmt.truncate(fmt.basename(proc.command, proc.name), name_width))
    return out
