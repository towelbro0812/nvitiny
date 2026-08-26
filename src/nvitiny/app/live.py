"""即時監看迴圈。

殘影的根因與對策
----------------
rich 的 ``Live`` 預設 ``screen=False``，重繪方式是把游標往上移 N 行再覆寫。
只要使用者用滑鼠滾輪往上捲、或內容一度高過視窗，游標的相對基準就會偏掉，
上一幀的殘骸就留在畫面上。這裡一律用 ``screen=True`` 走 alternate screen
buffer：那個緩衝區沒有 scrollback，滾輪不會捲動畫面，覆寫基準永遠正確。
代價是離開後畫面不留痕跡 —— 對監看工具反而是想要的行為。

另一半前提是版面高度必須夾在終端行數內，由 ``view.compose`` 保證。
"""

from __future__ import annotations

import contextlib
import os
import signal
import sys
import threading
from collections.abc import Callable

from rich.console import Console
from rich.live import Live
from rich.text import Text

from ..core.history import GpuHistory
from ..core.model import Snapshot
from ..view.compose import compose
from .keys import QUIT, KeyMap, KeyReader


def supported() -> bool:
    """非 TTY（例如導進管線）無法跑即時模式。"""
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


class LiveApp:
    def __init__(
        self,
        sample: Callable[[], Snapshot],
        interval: float = 1.0,
        keymap: KeyMap | None = None,
    ) -> None:
        self.sample = sample
        self.interval = interval
        self.keymap = keymap or KeyMap()
        self.console = Console()
        self.histories: dict[int, GpuHistory] = {}
        self._wake = threading.Event()
        self._running = True
        # 要新增按鍵行為，在 keys.DEFAULT_BINDINGS 加一列並在這裡註冊 handler
        self.handlers: dict[str, Callable[[], None]] = {QUIT: self.quit}

    def quit(self) -> None:
        self._running = False

    def _on_resize(self, *_: object) -> None:
        # 終端一改變大小就提前叫醒迴圈，不必等下一次取樣
        self._wake.set()

    def _record(self, snap: Snapshot) -> None:
        for gpu in snap.gpus:
            self.histories.setdefault(gpu.index, GpuHistory()).push(
                gpu.gpu_utilization, gpu.memory_percent,
            )

    def _handle_keys(self, reader: KeyReader) -> None:
        for key in reader.poll():
            action = self.keymap.action_for(key)
            handler = self.handlers.get(action) if action else None
            if handler:
                handler()

    def run(self) -> int:
        with contextlib.suppress(ValueError, OSError):
            signal.signal(signal.SIGWINCH, self._on_resize)

        with KeyReader() as reader, Live(
            console=self.console,
            screen=True,        # alternate screen：滾輪不捲動、無殘影
            auto_refresh=False,  # 自己控制節奏，避免與取樣搶拍
        ) as live:
            while self._running:
                try:
                    snap = self.sample()
                except Exception as exc:  # NVML 可能在驅動重載時暫時失效
                    live.update(Text(f"取樣失敗：{type(exc).__name__}: {exc}", style="red"),
                                refresh=True)
                else:
                    self._record(snap)
                    width, height = self.console.size
                    live.update(
                        compose(snap, width, height, self.histories),
                        refresh=True,
                    )

                self._wake.wait(timeout=self.interval)
                self._wake.clear()
                self._handle_keys(reader)
        return 0


def run(sample, interval: float = 1.0) -> int:
    return LiveApp(sample, interval).run()
