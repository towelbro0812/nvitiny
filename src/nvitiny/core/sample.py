"""資料來源：真實 NVML，或錄下來的 fixture。

兩者都產出同一組 model 的 dataclass，所以呈現層完全不知道資料是活的
還是罐頭的 —— 這也讓版面可以在沒有 GPU 的機器上開發與測試。

欄位對應只寫一次（``_build_gpu`` / ``_build_proc``），兩條來源共用。
先前 fixture 與 NVML 各寫一份，加一個欄位就得改兩處。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import GpuSnapshot, HostSnapshot, ProcSnapshot, Snapshot

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def na(value: Any) -> Any | None:
    """nvitop 的 NA 是 str 子類，直接用會讓版面印出 'N/A' 字樣佔位。"""
    return None if value is None or str(value) == "N/A" else value


# nvitop 把時脈收在巢狀物件裡，fixture 是攤平的
NESTED_PATHS = {
    "clock_sm": ("clock_infos", "sm"),
    "clock_sm_max": ("max_clock_infos", "sm"),
    "clock_memory": ("clock_infos", "memory"),
}


class _Reader:
    """把 dict 與物件的取值方式統一，讓建構邏輯只需要寫一次。"""

    def __init__(self, source: Any) -> None:
        self._source = source

    def __call__(self, name: str, default: Any = None) -> Any:
        value = self._read(self._source, name, default)
        if value is None and name in NESTED_PATHS:
            value = self._walk(NESTED_PATHS[name])
        return value

    @staticmethod
    def _read(node: Any, name: str, default: Any = None) -> Any:
        if isinstance(node, dict):
            return na(node.get(name, default))
        return na(getattr(node, name, default))

    def _walk(self, path: tuple[str, ...]) -> Any:
        node = self._source
        for name in path:
            node = self._read(node, name)
            if node is None:
                return None
        return node


def _build_proc(source: Any) -> ProcSnapshot:
    get = _Reader(source)
    return ProcSnapshot(
        pid=get("pid"),
        username=get("username"),
        gpu_memory=get("gpu_memory"),
        cpu_percent=get("cpu_percent"),
        memory_percent=get("memory_percent"),
        running_time=get("running_time_in_seconds"),
        command=get("command"),
        name=get("name"),
        type=get("type"),
    )


def _build_gpu(source: Any, procs: list[ProcSnapshot], host_memory_total: int | None) -> GpuSnapshot:
    get = _Reader(source)
    total = get("memory_total")
    return GpuSnapshot(
        index=get("index"),
        name=get("name"),
        memory_used=get("memory_used"),
        memory_total=total,
        memory_percent=get("memory_percent"),
        gpu_utilization=get("gpu_utilization"),
        memory_utilization=get("memory_utilization"),
        temperature=get("temperature"),
        fan_speed=get("fan_speed"),
        power_usage=get("power_usage"),
        power_limit=get("power_limit"),
        clock_sm=get("clock_sm"),
        clock_sm_max=get("clock_sm_max"),
        clock_memory=get("clock_memory"),
        processes=sorted(procs, key=lambda p: p.gpu_memory or 0, reverse=True),
        # GB10 / Jetson 上 GPU 與系統共用同一塊記憶體，實測比值剛好 1.0
        unified_memory=bool(total and host_memory_total and total == host_memory_total),
    )


def available_fixtures() -> list[str]:
    """內建的所有 fixture 名稱，依檔名排序。"""
    return sorted(path.stem for path in FIXTURE_DIR.glob("*.json"))


def from_fixture(name: str = "gb10") -> Snapshot:
    path = Path(name) if Path(name).exists() else FIXTURE_DIR / f"{name}.json"
    data = json.loads(path.read_text())
    host = data["host"]
    host_total = host.get("memory_total")
    return Snapshot(
        driver_version=data.get("driver_version"),
        cuda_version=data.get("cuda_version"),
        gpus=[
            _build_gpu(g, [_build_proc(p) for p in g.get("processes", [])], host_total)
            for g in data["gpus"]
        ],
        host=HostSnapshot(
            cpu_percent=host.get("cpu_percent"),
            memory_used=host.get("memory_used"),
            memory_total=host_total,
            memory_percent=host.get("memory_percent"),
        ),
    )


def from_live() -> Snapshot:
    """從 NVML 取樣。只用 nvitop.api（Apache-2.0），不碰 nvitop.tui（GPL-3.0）。"""
    from nvitop import Device, host  # 延後匯入：--demo 不需要有 GPU

    memory = host.virtual_memory()
    gpus = [
        _build_gpu(
            device.as_snapshot(),
            [_build_proc(p.as_snapshot()) for p in device.processes().values()],
            memory.total,
        )
        for device in Device.all()
    ]
    return Snapshot(
        driver_version=na(Device.driver_version()),
        cuda_version=na(Device.cuda_driver_version()),
        gpus=gpus,
        host=HostSnapshot(
            cpu_percent=host.cpu_percent(),
            memory_used=memory.used,
            memory_total=memory.total,
            memory_percent=memory.percent,
        ),
    )
