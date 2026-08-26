"""鍵盤輸入：解碼與綁定。

設計重點是**把按鍵解碼成語意名稱**（``up`` / ``pgup`` / ``q``）再去查綁定表，
而不是直接比對原始位元組。

這不只是為了好看。alternate screen 裡終端機沒有畫面可捲，會把滑鼠滾輪
轉譯成方向鍵送進 stdin（``ESC [ A`` / ``ESC [ B``）。舊版把裸 ESC 當離開鍵，
使用者一滾輪就會被判定按下 Esc 而結束。解碼成 ``up`` / ``down`` 之後，
沒有人綁定它們，滾輪就自然無作用 —— 是明確的無視，不是意外的正確。

要新增一個按鍵行為，只需要在 ``DEFAULT_BINDINGS`` 加一列，再於執行迴圈的
handler 表放進對應函式。
"""

from __future__ import annotations

import contextlib
import re
import select
import sys
import termios
import tty
from collections.abc import Iterator
from dataclasses import dataclass

ESC = "\x1b"
CTRL_C = "\x03"
CTRL_D = "\x04"
CSI_FINAL = re.compile(r"[@-~]")

# CSI / SS3 序列的結尾字元 → 語意名稱
_CSI_NAMES = {
    "A": "up", "B": "down", "C": "right", "D": "left",
    "H": "home", "F": "end",
}
_CSI_TILDE_NAMES = {"5": "pgup", "6": "pgdn", "3": "delete"}

QUIT = "quit"


@dataclass(frozen=True)
class Binding:
    keys: tuple[str, ...]
    action: str
    help: str


# 目前只綁離開。方向鍵與翻頁鍵已經會被解碼成語意名稱，要加行為
# 直接在這裡多一列即可，不必再碰解碼邏輯。
DEFAULT_BINDINGS: tuple[Binding, ...] = (
    Binding(("q", "Q", CTRL_C, CTRL_D), QUIT, "離開"),
)


class KeyMap:
    def __init__(self, bindings: tuple[Binding, ...] = DEFAULT_BINDINGS) -> None:
        self._bindings = bindings
        self._lookup = {key: b.action for b in bindings for key in b.keys}

    def action_for(self, key: str) -> str | None:
        return self._lookup.get(key)


class KeyReader:
    """非阻塞讀取並解碼按鍵。非 TTY 時安靜地什麼都不做。"""

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdin
        self._active = False

    def __enter__(self) -> KeyReader:
        if not self._stream.isatty():
            return self
        fd = self._stream.fileno()
        try:
            self._saved = termios.tcgetattr(fd)
        except (termios.error, ValueError):
            return self
        tty.setcbreak(fd)
        self._active = True
        return self

    def __exit__(self, *_: object) -> None:
        if self._active:
            with contextlib.suppress(termios.error, ValueError):
                termios.tcsetattr(self._stream.fileno(), termios.TCSADRAIN, self._saved)
            self._active = False

    def _readable(self) -> bool:
        return bool(select.select([self._stream], [], [], 0)[0])

    def poll(self) -> Iterator[str]:
        """把目前緩衝區裡的按鍵全部解碼吐出來。"""
        if not self._active:
            return
        while self._readable():
            char = self._stream.read(1)
            if not char:
                yield CTRL_D  # stdin 關閉，視同離開
                return
            if char == ESC:
                yield self._decode_escape()
            else:
                yield char

    def _decode_escape(self) -> str:
        """讀完一整段 ANSI 跳脫序列並轉成語意名稱。

        ESC 之後沒有後續位元組，代表使用者真的按了 Esc。
        """
        if not self._readable():
            return ESC
        intro = self._stream.read(1)
        if intro not in ("[", "O"):
            return ESC
        params = ""
        while self._readable():
            char = self._stream.read(1)
            if CSI_FINAL.match(char):
                if char == "~":
                    return _CSI_TILDE_NAMES.get(params, "unknown")
                return _CSI_NAMES.get(char, "unknown")
            params += char
        return "unknown"
