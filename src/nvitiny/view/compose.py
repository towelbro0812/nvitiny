"""照著 LayoutPlan 組裝畫面。所有算術都在 plan.py，這裡只管排版。"""

from __future__ import annotations

from rich.cells import cell_len
from rich.console import Group
from rich.text import Text

from ..core.history import GpuHistory
from ..core.model import GpuSnapshot, Snapshot
from ..view import sparkline, theme
from ..view import units as fmt
from ..view import widgets
from ..view.plan import XS, LayoutPlan, plan as make_plan

# 曲線標籤與上方對應的指標列對齊，讀者才知道畫的是哪一個
SPARK_LABEL_MEMORY = "M "
SPARK_LABEL_UTIL = "U "


def facts(gpu: GpuSnapshot, *, compact: bool) -> list[str]:
    """有值才出現的次要欄位。GB10 上 fan / power_limit / clock_mem 全缺。"""
    items = (
        fmt.celsius(gpu.temperature),
        fmt.watts(gpu.power_usage, gpu.power_limit, compact=compact),
        fmt.mhz(gpu.clock_sm),
        None if gpu.fan_speed is None else f"fan {gpu.fan_speed}%",
    )
    return [item for item in items if item]


def _header(gpu: GpuSnapshot, width: int, tier: str) -> Text:
    tag = f"GPU{gpu.index}"
    if tier == XS:
        return Text(tag, style=theme.HEADER)
    out = Text()
    out.append(tag, style=theme.HEADER)
    out.append("  ")
    out.append(fmt.truncate(gpu.name or gpu.short_name, width - len(tag) - 2), style=theme.LABEL)
    return out


def _memory_line(gpu: GpuSnapshot, width: int, *, inline_unified: bool) -> Text:
    body = f"{fmt.bytes_short(gpu.memory_used)}/{fmt.bytes_short(gpu.memory_total)}"
    out = Text()
    out.append("  ")
    out.append(body, style=theme.mem_color(gpu.memory_percent))
    # 統一記憶體必須標記，否則 122G 會被當成獨立顯存誤讀
    if gpu.unified_memory:
        gap = " " if inline_unified else "  "
        if width >= cell_len(body) + len(gap) + 10:
            out.append(f"{gap}unified", style=theme.DIM)
    return out


def _compact_header(gpu: GpuSnapshot, width: int, items: list[str]) -> Text:
    """XS：整張卡壓成一行 `GPU0   8%│ 13%│46°C`。"""
    out = Text()
    out.append(f"GPU{gpu.index} ", style=theme.HEADER)
    out.append(fmt.pct(gpu.memory_percent).strip().rjust(4), style=theme.mem_color(gpu.memory_percent))
    out.append("│", style=theme.RULE)
    out.append(fmt.pct(gpu.gpu_utilization).strip().rjust(4), style=theme.load_color(gpu.gpu_utilization))
    for item in items[:2]:
        if cell_len(out.plain) + 1 + cell_len(item) <= width:
            out.append("│", style=theme.RULE)
            out.append(item, style=theme.DIM)
    return out


def gpu_block(
    gpu: GpuSnapshot,
    layout: LayoutPlan,
    history: GpuHistory | None,
    right_width: int,
) -> list[Text]:
    width = layout.width
    items = facts(gpu, compact=layout.compact_facts)
    lines: list[Text] = []

    if layout.tier == XS:
        lines.append(_compact_header(gpu, width, items))
        lines.append(_memory_line(gpu, width, inline_unified=True))
    else:
        lines.append(_header(gpu, width, layout.tier))
        # 記憶體在上、使用率在下。次要欄位跟著「列的位置」而不是跟著指標走，
        # 所以溫度永遠在第一列
        lines.append(widgets.metric_row(
            "M", gpu.memory_percent, theme.mem_color(gpu.memory_percent), width,
            items[0] if items else None, theme.temp_color(gpu.temperature), right_width,
        ))
        lines.append(widgets.metric_row(
            "U", gpu.gpu_utilization, theme.load_color(gpu.gpu_utilization), width,
            items[1] if len(items) > 1 else None, theme.DIM, right_width,
        ))
        lines.append(_memory_line(gpu, width, inline_unified=False))
        if layout.show_cpu_column and len(items) > 2:
            lines.append(Text("  " + "  ".join(items[2:]), style=theme.DIM))

    lines += _spark_lines(gpu, layout, history)
    return lines


def _spark_lines(gpu: GpuSnapshot, layout: LayoutPlan, history: GpuHistory | None) -> list[Text]:
    if history is None or layout.spark_lines <= 0:
        return []
    memory = (SPARK_LABEL_MEMORY, history.memory, theme.mem_color(gpu.memory_percent))
    util = (SPARK_LABEL_UTIL, history.util, theme.load_color(gpu.gpu_utilization))
    # 兩條時照 M 上 U 下；只剩一條時留使用率 —— 記憶體多半長期不動，
    # 一條平線佔一行不划算
    series = [memory, util] if layout.spark_lines >= 2 else [util]

    out = []
    for label, hist, color in series:
        line = Text()
        line.append(label, style=theme.LABEL)
        line.append(sparkline.braille(hist.values, layout.width - len(label)), style=color)
        out.append(line)
    return out


def proc_block(gpu: GpuSnapshot, layout: LayoutPlan, limit: int) -> list[Text]:
    if limit <= 0:
        return []
    width = layout.width
    lines = [widgets.rule(width)]

    # 有東西被藏起來時，提示行也要算進預算裡，否則會被高度裁掉，
    # 變成默默少列 process —— 那比少顯示更糟
    overflow = len(gpu.processes) > limit
    shown = gpu.processes[: limit - 1] if overflow else gpu.processes
    for proc in shown:
        lines.append(widgets.proc_row(
            proc, width,
            show_user=layout.show_user_column,
            show_cpu=layout.show_cpu_column,
            gpu_memory_total=gpu.memory_total,
        ))
    hidden = len(gpu.processes) - len(shown)
    if hidden:
        # 中文是寬字元，窄屏放不下完整句子時退回極簡形式
        note = f"  … 另有 {hidden} 個 process" if width >= 22 else f"  … +{hidden}"
        lines.append(Text(fmt.truncate(note, width), style=theme.DIM))
    elif not gpu.processes:
        lines.append(Text(fmt.truncate("  無 process", width), style=theme.DIM))
    return lines


def version_line(snap: Snapshot, width: int) -> Text | None:
    drv, cuda = snap.driver_version, snap.cuda_version
    if not drv and not cuda:
        return None
    full = "  ".join(p for p in (f"drv {drv}" if drv else "", f"cuda {cuda}" if cuda else "") if p)
    compact = " ".join(p for p in (drv or "", f"cu{cuda}" if cuda else "") if p)
    return Text(fmt.truncate(full if width >= len(full) + 2 else compact, width), style=theme.DIM)


def host_line(snap: Snapshot, width: int) -> Text:
    host = snap.host
    left = Text()
    left.append("HOST ", style=theme.LABEL)
    left.append(f"cpu {host.cpu_percent:.0f}%", style=theme.load_color(host.cpu_percent))
    right = Text(
        f"ram {fmt.bytes_short(host.memory_used)}/{fmt.bytes_short(host.memory_total)}",
        style=theme.mem_color(host.memory_percent),
    )
    return widgets.justify(left, right, width)


def compose(
    snap: Snapshot,
    width: int,
    height: int,
    histories: dict[int, GpuHistory] | None = None,
) -> Group:
    histories = histories or {}
    layout = make_plan(
        width, height,
        [len(gpu.processes) for gpu in snap.gpus],
        has_sparks=bool(histories),
        has_version=bool(snap.driver_version or snap.cuda_version),
    )
    gpus = snap.gpus[: layout.gpus_shown]

    # 全域右欄寬：所有卡、所有列共用，bar 才會一致。少了這個，GPU0 的
    # 381W/450W 會讓它的 bar 比 GPU1 的短一格
    right_width = max(
        (cell_len(f) for gpu in gpus for f in facts(gpu, compact=layout.compact_facts)[:2]),
        default=0,
    )

    lines: list[Text] = []
    version = version_line(snap, width) if layout.show_version else None
    if version is not None:
        lines.append(version)

    for i, gpu in enumerate(gpus):
        if layout.separate_gpus and i:
            lines.append(Text(""))
        lines += gpu_block(gpu, layout, histories.get(gpu.index), right_width)
        lines += proc_block(gpu, layout, layout.proc_rows[i])

    if layout.hidden_gpus:
        note = (
            f"  … 另有 {layout.hidden_gpus} 張卡" if width >= 18
            else f"  … +{layout.hidden_gpus} GPU"
        )
        lines.append(Text(fmt.truncate(note, width), style=theme.DIM))
    if layout.show_host:
        lines.append(host_line(snap, width))

    # 單一守門點：不管上游怎麼算，送出去的每一行都保證不超過 width、
    # 總行數不超過 height。個別元件算錯不會變成畫面破圖。
    clipped = []
    for line in lines[:height]:
        line.truncate(width, overflow="ellipsis")
        line.no_wrap = True
        clipped.append(line)
    return Group(*clipped)
