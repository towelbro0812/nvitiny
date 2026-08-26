"""單次輸出。導進管線或指定尺寸時走這條。"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable

from rich.console import Console

from ..core.model import Snapshot
from ..view.compose import compose


def run(sample: Callable[[], Snapshot]) -> int:
    try:
        snap = sample()
    except Exception as exc:
        print(f"取樣失敗：{exc}", file=sys.stderr)
        return 1
    if not snap.gpus:
        print("找不到 NVIDIA GPU。", file=sys.stderr)
        return 1

    width, height = shutil.get_terminal_size(fallback=(80, 24))
    # 單次輸出沒有歷史可累積，所以不畫曲線
    Console(width=width, height=height).print(compose(snap, width, height))
    return 0
