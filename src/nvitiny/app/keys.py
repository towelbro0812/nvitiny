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
import sys
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

# Windows 主控台的功能鍵是兩個字元：前綴 \x00 或 \xe0，再接掃描碼
_WIN_PREFIXES = ("\x00", "\xe0")
_WIN_SCAN_NAMES = {
    "H": "up", "P": "down", "M": "right", "K": "left",
    "G": "home", "O": "end", "I": "pgup", "Q": "pgdn", "S": "delete",
}

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


class _BaseKeyReader:
    """非阻塞讀取並解碼按鍵。非 TTY 時安靜地什麼都不做。

    子類別只需提供 ``_readable`` / ``_read`` 與進出終端模式的細節。
    """

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdin
        self._active = False

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self._active = False

    def _readable(self) -> bool:
        raise NotImplementedError

    def _read(self) -> str:
        raise NotImplementedError

    def _decode(self, char: str) -> str:
        if char == ESC:
            return self._decode_escape()
        return char

    def poll(self) -> Iterator[str]:
        """把目前緩衝區裡的按鍵全部解碼吐出來。"""
        if not self._active:
            return
        while self._readable():
            char = self._read()
            if not char:
                yield CTRL_D  # stdin 關閉，視同離開
                return
            yield self._decode(char)

    def _decode_escape(self) -> str:
        """讀完一整段 ANSI 跳脫序列並轉成語意名稱。

        ESC 之後沒有後續位元組，代表使用者真的按了 Esc。
        """
        if not self._readable():
            return ESC
        intro = self._read()
        if intro not in ("[", "O"):
            return ESC
        params = ""
        while self._readable():
            char = self._read()
            if CSI_FINAL.match(char):
                if char == "~":
                    return _CSI_TILDE_NAMES.get(params, "unknown")
                return _CSI_NAMES.get(char, "unknown")
            params += char
        return "unknown"


# 平台實作整段放進 sys.platform 分支：型別檢查器會把另一個平台的分支
# 視為不可達而略過，不會對著不存在的 termios / msvcrt 報未定義
if sys.platform == "win32":
    import msvcrt

    class KeyReader(_BaseKeyReader):
        """Windows 主控台：msvcrt 直接讀按鍵，不需要切換終端模式。"""

        def __enter__(self) -> KeyReader:
            self._active = self._stream.isatty()
            return self

        def _readable(self) -> bool:
            return msvcrt.kbhit()

        def _read(self) -> str:
            return msvcrt.getwch()

        def _decode(self, char: str) -> str:
            if char in _WIN_PREFIXES:
                scan = self._read() if self._readable() else ""
                return _WIN_SCAN_NAMES.get(scan, "unknown")
            return super()._decode(char)

else:
    import select
    import termios
    import tty

    class KeyReader(_BaseKeyReader):
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

        def _read(self) -> str:
            return self._stream.read(1)
