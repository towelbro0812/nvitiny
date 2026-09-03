"""版面決策：在給定的寬高裡，決定「顯示什麼」。

這裡是純函式 —— 輸入是幾個整數，輸出是一個描述畫面組成的 dataclass。
不碰 rich、不碰 GPU 資料，所以高度預算可以直接單元測試，不必渲染整張
畫面再用正則反推。

分級不是為了好看，是為了決定「哪些欄位要消失」。每一級都保證不會橫向
溢位，也不會因為終端太窄而拒絕渲染 —— 那正是 nvitop 在 79 欄以下做的事
（nvitop/tui/tui.py:177）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

XS, S, M, L = "xs", "s", "m", "l"

# 每張卡的固定資訊行數（標題 + bar 們 + 記憶體，不含分隔線、曲線與 process）
FIXED_LINES = {XS: 2, S: 4, M: 4, L: 4}
# 高度不足時的降級路徑
DOWNGRADE = {L: M, M: S, S: XS}

# 24 欄是 bar 的下限：`U `(2) + bar(>=12) + ` 13%`(4) + `  46°C`(6)
BAR_MIN_WIDTH = 24
# 低於這個寬度時，process 的使用者欄要讓位給指令名稱
USER_COL_MIN_WIDTH = 34
# 分級門檻
TIER_BREAKPOINTS = ((BAR_MIN_WIDTH, XS), (56, S), (79, M))

# 一張卡要列出第一個 process，得付分隔線 + 該列共兩行
FIRST_PROC_COST = 2


@dataclass(frozen=True)
class LayoutPlan:
    """畫面組成。compose 只負責照著這份計畫組裝，不再自己做算術。"""

    tier: str
    width: int
    height: int
    gpus_shown: int
    hidden_gpus: int
    spark_lines: int
    show_status: bool
    separate_gpus: bool
    proc_rows: tuple[int, ...]

    @property
    def show_user_column(self) -> bool:
        return self.tier != XS and self.width >= USER_COL_MIN_WIDTH

    @property
    def show_cpu_column(self) -> bool:
        return self.tier in (M, L)

    @property
    def show_proc_detail(self) -> bool:
        """process 的「跑了多久」與 C/G 型別欄，也是 L 與 M 唯一的差別。"""
        return self.tier == L

    @property
    def compact_facts(self) -> bool:
        """窄寬度時功耗只留用量，把分母的位置讓給 bar。"""
        return self.width < USER_COL_MIN_WIDTH

    @property
    def total_lines(self) -> int:
        per_gpu = FIXED_LINES[self.tier] + self.spark_lines
        procs = sum(FIRST_PROC_COST - 1 + rows for rows in self.proc_rows if rows)
        return (
            int(self.show_status)
            + self.gpus_shown * per_gpu
            + procs
            + int(bool(self.hidden_gpus))
            + (self.gpus_shown - 1 if self.separate_gpus else 0)
        )


def tier_for(width: int) -> str:
    for threshold, tier in TIER_BREAKPOINTS:
        if width < threshold:
            return tier
    return L


def _fit_tier(width: int, height: int, gpu_count: int) -> str:
    """高度不足時逐級降版面。

    一張卡的區塊寧可整個不顯示，也不能被切成一半 —— 只剩記憶體 bar
    沒有使用率 bar 會讓人誤判那張卡的狀態。
    """
    tier = tier_for(width)
    while tier != XS and gpu_count * FIXED_LINES[tier] > height:
        tier = DOWNGRADE[tier]
    return tier


def _allocate_proc_rows(budget: int, needs: Sequence[int]) -> tuple[int, ...]:
    """輪流分配：閒置卡用不完的額度會自動流向 process 多的卡。

    平均切的話，只有一個 process 的閒置卡會佔著跟滿載卡一樣多的額度。
    """
    alloc = [0] * len(needs)
    remaining = max(0, budget)
    progressed = True
    while remaining > 0 and progressed:
        progressed = False
        for i, need in enumerate(needs):
            if alloc[i] >= need:
                continue
            cost = FIRST_PROC_COST if alloc[i] == 0 else 1
            if remaining >= cost:
                alloc[i] += 1
                remaining -= cost
                progressed = True
    return tuple(alloc)


def plan(
    width: int,
    height: int,
    proc_counts: Sequence[int],
    *,
    has_sparks: bool = False,
) -> LayoutPlan:
    """算出這個尺寸下要顯示什麼。

    proc_counts 是每張卡的 process 數量 —— 只需要數量，不需要內容，
    這讓整個決策層跟 GPU 資料完全解耦。
    """
    gpu_count = len(proc_counts)
    tier = _fit_tier(width, height, max(1, gpu_count))
    per_gpu = FIXED_LINES[tier]

    # 降到 XS 仍放不下所有卡，就少顯示幾張並留一行說明
    shown = gpu_count
    hidden = 0
    if gpu_count * per_gpu > height:
        shown = max(0, (height - 1) // per_gpu)
        hidden = gpu_count - shown
    needs = list(proc_counts[:shown])

    budget = height - shown * per_gpu - (1 if hidden else 0)

    # 有 process 的卡至少要付得起第一列（= 分隔線 + 一行）。就算那一行
    # 最後只放得下「… 另有 N 個」提示，也比靜靜藏掉整份清單好。
    floor = sum(FIRST_PROC_COST for need in needs if need)

    # 曲線幾條：兩條(M+U) > 一條(U) > 不畫
    spark_lines = 0
    if has_sparks and shown:
        room = budget - floor
        if room >= 2 * shown:
            spark_lines = 2
        elif room >= shown:
            spark_lines = 1
    budget -= spark_lines * shown

    # 狀態列輸給「讓每張卡的 process 清單有個交代」
    show_status = budget - 1 >= floor
    if show_status:
        budget -= 1

    proc_rows = _allocate_proc_rows(budget, needs)

    draft = LayoutPlan(
        tier=tier, width=width, height=height,
        gpus_shown=shown, hidden_gpus=hidden, spark_lines=spark_lines,
        show_status=show_status,
        separate_gpus=False, proc_rows=proc_rows,
    )
    # 多卡且高度有餘時，用空行分隔，避免上一張卡的 process 黏著下一張卡的標題
    if shown > 1 and draft.total_lines + (shown - 1) <= height:
        return LayoutPlan(**{**draft.__dict__, "separate_gpus": True})
    return draft
