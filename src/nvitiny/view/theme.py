"""顏色門檻。低飽和為主，只有真的該注意的數字才亮起來。"""

from __future__ import annotations

# (門檻, 顏色) 由低到高，取第一個大於等於值的門檻
LOAD_STEPS = ((40, "green"), (75, "yellow"), (101, "red"))
TEMP_STEPS = ((60, "green"), (80, "yellow"), (1000, "red"))
MEM_STEPS = ((50, "cyan"), (85, "yellow"), (101, "red"))

DIM = "dim"
LABEL = "bright_black"
HEADER = "bold"
RULE = "bright_black"
BAR_EMPTY = "bright_black"


def _pick(steps: tuple[tuple[int, str], ...], value: float | None) -> str:
    if value is None:
        return DIM
    for threshold, color in steps:
        if value < threshold:
            return color
    return steps[-1][1]


def load_color(pct: float | None) -> str:
    return _pick(LOAD_STEPS, pct)


def mem_color(pct: float | None) -> str:
    return _pick(MEM_STEPS, pct)


def temp_color(celsius: float | None) -> str:
    return _pick(TEMP_STEPS, celsius)
