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

from nvitiny.view.compose import compose, status_line, version_forms
from nvitiny.view.plan import BAR_MIN_WIDTH, FIXED_LINES, S, tier_for

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


@pytest.fixture(scope="module", params=[(w, h) for w in WIDTHS for h in HEIGHTS])
def size(request):
    return request.param


@pytest.fixture(scope="module", params=["sparks", "plain"])
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


TIME_COL = re.compile(r"\d+:\d{2}:\d{2}")
MEM_BODY = re.compile(r"\d+(\.\d+)?[BKMGT]/\d+(\.\d+)?[BKMGT]")
STATUS_WIDTHS = list(range(12, 120, 3))


@pytest.mark.parametrize("width", STATUS_WIDTHS)
def test_status_line_never_sacrifices_the_live_numbers(snapshot, width):
    """版本是靜態資訊，任何寬度都先砍它；CPU / RAM 一格都不讓。"""
    line = status_line(snapshot, width).plain
    assert line.startswith("C ")
    assert "  R " in line


@pytest.mark.parametrize("width", STATUS_WIDTHS)
def test_status_line_only_overflows_on_the_host_numbers(snapshot, width):
    """版本欄放不下就整段不放 —— 絕不塞進去再讓 compose 截斷。"""
    line = status_line(snapshot, width).plain
    if cell_len(line) > width:
        assert not any(form and form in line for form in version_forms(snapshot))


def test_status_line_never_gains_information_as_it_narrows(snapshot):
    """降級階梯必須單調：窄一格只能少東西，不能多。"""
    seen = [cell_len(status_line(snapshot, w).plain) for w in range(120, 11, -1)]
    assert seen == sorted(seen, reverse=True), seen


def test_version_labels_shrink_before_the_versions_themselves(snapshot):
    """`drv X  cuda Y` -> `X cuY` 只縮標籤，兩個版本號都還在。"""
    forms = version_forms(snapshot)
    widths = [cell_len(f) for f in forms]
    assert widths == sorted(widths, reverse=True), forms
    assert forms[-1] == ""
    if snapshot.driver_version and snapshot.cuda_version:
        compact = forms[1]
        assert snapshot.driver_version in compact
        assert snapshot.cuda_version in compact
        assert "drv" not in compact


@pytest.mark.parametrize("width", [40, 60, 78, 79, 100, 140])
def test_proc_detail_columns_are_what_makes_l_tier_l(snapshot, width):
    """L 與 M 的固定行數相同，這兩欄是 79 欄門檻僅存的理由。"""
    lines = render(snapshot, width, 40)
    proc_lines = [line for line in lines if re.match(r"\s*\d+ ", line)]
    assert proc_lines, "高度足夠卻沒有 process 列"
    assert all(TIME_COL.search(line) for line in proc_lines) == (tier_for(width) == "l")


@pytest.mark.parametrize("width", [40, 56, 60, 79, 100, 140])
def test_secondary_facts_never_occupy_their_own_line(snapshot, width):
    """時脈與風扇掛在記憶體行尾巴，不自己佔一行。"""
    orphans = [
        line for line in render(snapshot, width, 40)
        if ("MHz" in line or "fan " in line) and not MEM_BODY.search(line)
    ]
    assert not orphans, orphans
