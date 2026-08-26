"""版面決策的單元測試。

plan() 是純函式，所以這些不變量可以直接斷言，不必渲染整張畫面再用正則
反推 —— 先前所有的版面 bug 都出在這一層的算術裡。
"""

from __future__ import annotations

import pytest

from nvitiny.view.plan import FIRST_PROC_COST, FIXED_LINES, XS, plan, tier_for

SIZES = [(w, h) for w in range(12, 130, 3) for h in range(3, 40, 2)]
GPU_SETS = ([3], [2, 1], [0], [5, 5, 5, 5], [])


@pytest.mark.parametrize(("width", "height"), SIZES)
@pytest.mark.parametrize("procs", GPU_SETS)
@pytest.mark.parametrize("sparks", [True, False])
def test_never_exceeds_height(width, height, procs, sparks):
    p = plan(width, height, procs, has_sparks=sparks)
    assert p.total_lines <= height


@pytest.mark.parametrize(("width", "height"), SIZES)
@pytest.mark.parametrize("procs", GPU_SETS)
def test_gpu_blocks_are_never_split(width, height, procs):
    """一張卡的區塊寧可整個不顯示，也不能被切一半 —— 只剩記憶體 bar
    沒有使用率 bar 會讓人誤判那張卡的狀態。"""
    p = plan(width, height, procs, has_sparks=True)
    assert p.gpus_shown + p.hidden_gpus == len(procs)
    if p.gpus_shown:
        needed = p.gpus_shown * (FIXED_LINES[p.tier] + p.spark_lines)
        assert needed <= height


@pytest.mark.parametrize(("width", "height"), SIZES)
@pytest.mark.parametrize("procs", GPU_SETS)
def test_processes_are_never_silently_hidden(width, height, procs):
    """只要還付得起一列，有 process 的卡就必須分到 —— 那一列就算只放得下
    「… 另有 N 個」提示，也比整份清單無聲消失好。

    付不起的情況是真的物理限制：一列的成本是「分隔線 + 該行」共兩行，
    多卡窄高度時（例如 4 張卡擠在 17 行）固定資訊就吃光了預算。
    """
    p = plan(width, height, procs, has_sparks=True)
    spare = height - p.total_lines
    if spare < FIRST_PROC_COST:
        return
    starved = [i for i in range(p.gpus_shown) if procs[i] and p.proc_rows[i] == 0]
    assert not starved, f"還有 {spare} 行可用，卻沒給 GPU{starved} 任何交代"


def test_idle_gpu_returns_unused_rows_to_busy_one():
    """平均切的話，只有一個 process 的閒置卡會佔著跟滿載卡一樣多的額度。"""
    p = plan(40, 14, [5, 1], has_sparks=False)
    assert p.proc_rows[0] > p.proc_rows[1]
    assert p.proc_rows[1] == 1


def test_tier_degrades_when_height_is_short():
    wide, procs = 100, [1, 1, 1]
    assert tier_for(wide) == "l"
    assert plan(wide, 30, procs).tier == "l"
    assert plan(wide, 10, procs).tier == XS


def test_spark_lines_degrade_before_processes():
    """犧牲順序：process 列數 → 版本行 → 第二條曲線 → 第一條曲線。"""
    seen = [plan(40, h, [3], has_sparks=True).spark_lines for h in range(20, 5, -1)]
    assert seen == sorted(seen, reverse=True), seen
    assert seen[0] == 2
    assert seen[-1] == 0


def test_no_sparks_means_no_reserved_line():
    """沒有曲線資料就不能預留那一行，否則單次輸出會白白浪費一行高度。"""
    with_sparks = plan(40, 12, [3], has_sparks=True)
    without = plan(40, 12, [3], has_sparks=False)
    assert without.spark_lines == 0
    assert sum(without.proc_rows) >= sum(with_sparks.proc_rows)


def test_empty_gpu_list_does_not_crash():
    p = plan(40, 20, [], has_sparks=True)
    assert p.gpus_shown == 0
    assert p.proc_rows == ()
