"""渲染不變量。

每一條都對應一個真的壞掉過的地方。plan 那層的算術由 test_plan 負責，
這裡驗的是「畫出來之後」的性質。
"""

from __future__ import annotations

import io
import re

import pytest
from rich.cells import cell_len
from rich.console import Console

from nvitiny.view.compose import compose
from nvitiny.view.plan import BAR_MIN_WIDTH, FIXED_LINES, S

BAR = re.compile(r"▕([█░]*)▏")
SPARK_CHARS = "⣀⣤⣶⣿⣷⣦⣴⠀⣠⣄⣆⣇⣧⣼⣾⡇⡄⡆⡀⢀⢠⢰⢸⣸"
HIDDEN = re.compile(r"另有|\+\d")
MIN_BAR_CELLS = 8

WIDTHS = range(16, 200, 3)
HEIGHTS = range(3, 50, 2)


def render(snap, width, height, histories=None):
    console = Console(width=width, height=height, file=io.StringIO(), no_color=True)
    console.print(compose(snap, width, height, histories))
    return console.file.getvalue().rstrip("\n").split("\n")


def gpu_blocks(lines):
    """按 GPU 標題切開。跨卡比較相鄰列會誤判順序，必須逐卡檢查。"""
    blocks = []
    for line in lines:
        if line.startswith("GPU"):
            blocks.append([])
        if blocks:
            blocks[-1].append(line)
    return blocks


@pytest.fixture(params=[(w, h) for w in WIDTHS for h in HEIGHTS])
def size(request):
    return request.param


@pytest.fixture(params=["sparks", "plain"])
def frame(request, snapshot, histories, size):
    width, height = size
    hist = histories if request.param == "sparks" else None
    return width, height, render(snapshot, width, height, hist), snapshot


def test_never_overflows(frame):
    width, height, lines, _ = frame
    assert all(cell_len(line.rstrip()) <= width for line in lines)
    assert len(lines) <= height


def test_bars_share_one_width(frame):
    """右欄寬度若只在同一張卡內共用，GPU0 的 381W/450W 會讓它的 bar
    比 GPU1 的短一格。"""
    *_, lines, _ = frame
    widths = {len(m.group(1)) for line in lines for m in [BAR.search(line)] if m}
    assert len(widths) <= 1, widths


def test_bars_are_legible_or_absent(frame):
    width, height, lines, snap = frame
    bars = [len(m.group(1)) for line in lines for m in [BAR.search(line)] if m]
    if bars:
        assert min(bars) >= MIN_BAR_CELLS
    elif width >= BAR_MIN_WIDTH and height >= len(snap.gpus) * FIXED_LINES[S] + 2:
        pytest.fail("寬高都足夠卻沒有 bar")


def test_no_wasted_height_while_hiding(frame):
    _, height, lines, _ = frame
    if len(lines) < height:
        assert not any(HIDDEN.search(line) for line in lines)


def test_memory_row_sits_above_util_row(frame):
    *_, lines, _ = frame
    for block in gpu_blocks(lines):
        rows = [line for line in block if BAR.search(line)]
        if rows:
            assert len(rows) == 2
            assert rows[0].startswith("M ") and rows[1].startswith("U ")


def test_sparklines_are_labelled_and_ordered(frame):
    *_, lines, _ = frame
    for block in gpu_blocks(lines):
        rows = [line for line in block if any(c in line for c in SPARK_CHARS)]
        assert all(row.startswith(("M ", "U ")) for row in rows), rows
        assert len(rows) <= 2
        if len(rows) == 2:
            assert rows[0].startswith("M ") and rows[1].startswith("U ")
        elif len(rows) == 1:
            # 只剩一條時留使用率：記憶體多半長期不動，平線佔一行不划算
            assert rows[0].startswith("U ")
