"""與資料來源無關的快照結構。

所有欄位都可能是 None —— GB10 這類機器上 fan_speed / power_limit /
clock_memory 都拿不到，版面必須有能力整欄消失而不是印 'N/A' 佔位。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProcSnapshot:
    pid: int
    username: str | None
    gpu_memory: int | None
    cpu_percent: float | None
    memory_percent: float | None
    running_time_human: str | None
    command: str | None
    name: str | None
    type: str | None


@dataclass(frozen=True)
class GpuSnapshot:
    index: int
    name: str | None
    memory_used: int | None
    memory_total: int | None
    memory_percent: float | None
    gpu_utilization: int | None
    memory_utilization: int | None
    temperature: int | None
    fan_speed: int | None
    power_usage: int | None
    power_limit: int | None
    clock_sm: int | None
    clock_memory: int | None
    processes: list[ProcSnapshot] = field(default_factory=list)
    unified_memory: bool = False

    @property
    def short_name(self) -> str:
        """'NVIDIA GeForce RTX 4090' -> 'RTX 4090'，窄屏用。"""
        if not self.name:
            return f"GPU{self.index}"
        n = self.name.replace("NVIDIA ", "").replace("GeForce ", "")
        return n.strip() or f"GPU{self.index}"


@dataclass(frozen=True)
class HostSnapshot:
    cpu_percent: float | None
    memory_used: int | None
    memory_total: int | None
    memory_percent: float | None


@dataclass(frozen=True)
class Snapshot:
    gpus: list[GpuSnapshot]
    host: HostSnapshot
    driver_version: str | None = None
    cuda_version: str | None = None
