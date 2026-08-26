"""即時模式的端到端測試。

必須在真的 pty 裡跑 —— 用一般管線會走非 TTY 的退回路徑，鍵盤與
alternate screen 那些程式碼完全不會執行，等於什麼都沒驗到。
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import sys
import termios
import time

import pytest

ALT_ON, ALT_OFF = "\x1b[?1049h", "\x1b[?1049l"

# 直接驅動 LiveApp，不透過 CLI —— 正式的命令列不該為了讓測試餵假資料
# 而留一個旗標。這裡驗的是 Live / 按鍵 / alternate screen，跟參數解析無關。
DRIVER = (
    "from nvitiny.app.live import LiveApp;"
    "from nvitiny.core.sample import from_fixture;"
    "raise SystemExit(LiveApp(lambda: from_fixture('gb10'), 0.4).run())"
)
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
SMALL, LARGE = (20, 40), (24, 72)


def set_size(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def drain(fd, seconds):
    end, chunks = time.time() + seconds, []
    while time.time() < end:
        if not select.select([fd], [], [], 0.1)[0]:
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks).decode("utf-8", "replace")


@pytest.fixture(scope="module")
def session():
    """跑一輪完整的即時模式，把各階段的輸出留給各個測試檢查。"""
    master, slave = pty.openpty()
    set_size(slave, *SMALL)
    proc = subprocess.Popen(
        [sys.executable, "-c", DRIVER],
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "TERM": "xterm-256color"},
        close_fds=True,
    )
    os.close(slave)

    initial = drain(master, 2.0)
    # 滾輪在 alternate screen 裡會被轉譯成方向鍵，絕不可以被當成離開鍵
    os.write(master, b"\x1b[A\x1b[B\x1b[A" * 6)
    scrolled = drain(master, 1.5)
    alive_after_scroll = proc.poll() is None

    set_size(master, *LARGE)
    resized = drain(master, 2.0)

    os.write(master, b"q")
    final = drain(master, 1.5)   # 還原 alternate screen 的序列在這一段
    try:
        code = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = None
    os.close(master)
    return {
        "initial": initial, "scrolled": scrolled, "resized": resized,
        "final": final, "alive_after_scroll": alive_after_scroll, "code": code,
        "all": initial + scrolled + resized + final,
    }


def test_uses_alternate_screen(session):
    """預設的 screen=False 靠游標上移覆寫重繪，滾輪一捲基準就錯位而留下殘影。"""
    assert ALT_ON in session["all"]
    assert ALT_OFF in session["all"]


def test_renders_bars_at_40_columns(session):
    assert "▕" in session["initial"]


def test_keeps_redrawing(session):
    assert session["initial"].count("GPU0") >= 2


def test_scrolling_does_not_quit(session):
    assert session["alive_after_scroll"]
    assert session["scrolled"].count("GPU0") >= 1


def test_resize_switches_to_wider_layout(session):
    """2405MHz 這類次要欄位只在 56 欄以上出現，可以用來證明真的重新分級了。"""
    assert "MHz" in session["resized"]
    assert "MHz" not in session["initial"]


def test_redraw_respects_terminal_width(session):
    frames = re.split(r"\x1b\[2J|\x1b\[H", session["resized"])
    overflowing = [
        line for frame in frames
        for line in ANSI.sub("", frame).split("\n")
        if len(line.rstrip()) > LARGE[1]
    ]
    assert not overflowing, overflowing[:2]


def test_quit_key_exits_cleanly(session):
    assert session["code"] == 0
