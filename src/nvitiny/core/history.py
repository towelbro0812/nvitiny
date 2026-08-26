"""取樣歷史。只負責存，不負責畫 —— 繪圖在 view/sparkline.py。"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

DEFAULT_MAXLEN = 512


class History:
    """定長環狀取樣緩衝。"""

    def __init__(self, maxlen: int = DEFAULT_MAXLEN) -> None:
        self._buf: deque[float] = deque(maxlen=maxlen)

    def push(self, value: float | None) -> None:
        # None（欄位缺值）當成 0，曲線才不會出現斷點
        self._buf.append(float(value) if value is not None else 0.0)

    @property
    def values(self) -> Sequence[float]:
        return self._buf

    def __len__(self) -> int:
        return len(self._buf)


class GpuHistory:
    """一張卡的兩條曲線。

    使用率與記憶體分開存，因為兩者的變化型態完全不同：使用率是高頻抖動，
    記憶體通常是階梯狀（配置後就長期不動）。
    """

    def __init__(self, maxlen: int = DEFAULT_MAXLEN) -> None:
        self.util = History(maxlen)
        self.memory = History(maxlen)

    def push(self, util: float | None, memory: float | None) -> None:
        self.util.push(util)
        self.memory.push(memory)
