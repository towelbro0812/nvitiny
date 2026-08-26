"""版面模擬：用 fixture 把各種寬度一次畫出來，不需要 GPU。

給使用者預覽用（`nvitiny --demo`），也給開發時調版面用。合成曲線的種子
固定，所以每次跑出來一樣，方便比對版面差異。
"""

from __future__ import annotations

import math

from rich.console import Console

from ..core.history import GpuHistory
from ..core.sample import available_fixtures, from_fixture
from ..view.compose import compose
from ..view.plan import tier_for
from ..view.units import truncate

PRESETS = (
    (20, 14, "XS：太窄，退回單行"),
    (25, 16, "最窄 bar 模式"),
    (40, 20, "手機直立（主要目標）"),
    (60, 22, "手機橫放 / 分割 pane"),
    (100, 24, "一般桌機終端"),
)


def synth_history(seed: float, samples: int = 240) -> GpuHistory:
    """合成兩條型態不同的曲線，用來檢查並排時分不分得出來。

    使用率：慢波 + 快波 + 週期性尖峰（高頻抖動）
    記憶體：階梯狀單調上升偶爾釋放（模擬配置行為）
    """
    history = GpuHistory()
    memory = 12.0
    for i in range(samples):
        base = 45 + 32 * math.sin(i / 21 + seed)
        ripple = 9 * math.sin(i / 3.3 + seed * 2)
        spike = 22 if (i + int(seed * 7)) % 47 < 3 else 0
        util = max(0.0, min(100.0, base + ripple + spike))

        if (i + int(seed * 11)) % 31 == 0:
            memory = min(94.0, memory + 14)      # 一次配置一大塊
        elif (i + int(seed * 5)) % 97 == 0:
            memory = max(8.0, memory - 26)       # 偶爾釋放
        history.push(util, memory)
    return history


def _render_fixture(name: str, outer: Console) -> None:
    snap = from_fixture(name)
    histories = {gpu.index: synth_history(gpu.index * 1.7) for gpu in snap.gpus}
    cards = f"{len(snap.gpus)} 張卡"

    for width, height, note in PRESETS:
        console = Console(width=width, height=height, force_terminal=True)
        outer.print()
        outer.print(
            f"[bold]{name}[/bold] [dim]({cards})[/dim]  "
            f"[bold]{width}x{height}[/bold]  "
            f"[yellow]tier={tier_for(width)}[/yellow]  [dim]{truncate(note, 40)}[/dim]",
        )
        console.print("[bright_black]" + "┈" * width + "[/bright_black]")
        console.print(compose(snap, width, height, histories))
        console.print("[bright_black]" + "┈" * width + "[/bright_black]")


def run() -> int:
    """把每個內建 fixture 在每種預設寬度下都畫一遍。

    說明文字是 demo 自己的框架，用真實終端寬度印，才不會被模擬寬度截斷；
    只有 ┈ 分隔線用模擬寬度，用來標出版面的實際邊界。
    """
    outer = Console()
    for name in available_fixtures():
        _render_fixture(name, outer)
    return 0
