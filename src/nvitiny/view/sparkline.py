"""Sparkline：嵌在一行文字裡的迷你走勢圖，沒有座標軸與圖例。

只看形狀，絕對值交給旁邊的 bar 與百分比數字。純函式，不持有狀態 ——
取樣歷史在 core/history.py。

Braille 一格是 2 欄寬 x 4 列高的點陣，所以一個字元塞得下兩個取樣點、
每點四級高度 —— 在 30 欄的螢幕上仍能顯示 60 個取樣點的趨勢。

點位編號（Unicode U+2800 起算的 bit）：
    左欄由上而下 dot1 0x01 / dot2 0x02 / dot3 0x04 / dot7 0x40
    右欄由上而下 dot4 0x08 / dot5 0x10 / dot6 0x20 / dot8 0x80
長條由底部往上長，所以取的是「由下而上」的順序。
"""

from __future__ import annotations

from collections.abc import Sequence

BRAILLE_BASE = 0x2800
# 由下而上，讓 bits[:h] 直接就是填滿 h 格的長條
_LEFT_BOTTOM_UP = (0x40, 0x04, 0x02, 0x01)
_RIGHT_BOTTOM_UP = (0x80, 0x20, 0x10, 0x08)

def _cell(left: int, right: int) -> str:
    bits = 0
    for bit in _LEFT_BOTTOM_UP[:left]:
        bits |= bit
    for bit in _RIGHT_BOTTOM_UP[:right]:
        bits |= bit
    return chr(BRAILLE_BASE | bits)


def _quantize(values: Sequence[float], ceiling: float, levels: int) -> list[int]:
    if ceiling <= 0:
        return [0] * len(values)
    out = []
    for value in values:
        frac = max(0.0, min(1.0, value / ceiling))
        level = round(frac * levels)
        # 非零的值至少給一格，否則低負載看起來跟完全閒置一樣
        out.append(max(1, level) if frac > 0 and level == 0 else level)
    return out


def _tail(values: Sequence[float], count: int) -> list[float]:
    """取最後 count 個取樣點，不足就靠右對齊 —— 新資料從右邊長出來。"""
    recent = list(values)[-count:]
    return [0.0] * (count - len(recent)) + recent


def braille(values: Sequence[float], width: int, ceiling: float = 100.0) -> str:
    """每格兩個取樣點、四級高度。"""
    if width <= 0:
        return ""
    levels = _quantize(_tail(values, width * 2), ceiling, 4)
    return "".join(_cell(levels[i], levels[i + 1]) for i in range(0, len(levels), 2))
