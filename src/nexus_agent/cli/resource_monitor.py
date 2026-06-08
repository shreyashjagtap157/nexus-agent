"""Per-second resource monitor for the welcome panel.

Samples CPU, RAM, VRAM, and GPU usage once per second — but only while at
least one consumer is "subscribed" (e.g. the welcome panel is rendered).
When nothing is visible, the sampler sleeps so it costs ~0% CPU.

Public API:
    monitor = ResourceMonitor.get()
    monitor.subscribe()    # panel became visible
    snap = monitor.snapshot()  # read current sample (cheap)
    monitor.unsubscribe()  # panel hidden
    monitor.stop()         # shutdown thread on app exit

All sampling failures degrade gracefully (return zeros / Nones) so a
missing psutil or absent nvidia-smi never crashes the UI.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover - optional dep
    psutil = None  # type: ignore
    _HAS_PSUTIL = False


@dataclass
class ResourceSnapshot:
    """One sample of system resource usage."""
    cpu_percent: float = 0.0
    cpu_threads: int = 0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    gpu_percent: int = 0
    vram_used_gb: float = 0.0
    vram_total_gb: float = 0.0
    timestamp: float = 0.0

    @property
    def ram_str(self) -> str:
        if self.ram_total_gb <= 0:
            return "—"
        return f"{self.ram_used_gb:.1f}G/{self.ram_total_gb:.0f}G"

    @property
    def vram_str(self) -> str:
        if self.vram_total_gb <= 0:
            return ""
        return f"{self.vram_used_gb:.1f}G/{self.vram_total_gb:.0f}G"


class ResourceMonitor:
    """Background sampler with subscription-based activation.

    Singleton per process. Thread-safe. A single daemon thread does the
    sampling; consumers only see a cached snapshot, so reads are O(1).
    """

    _instance: Optional["ResourceMonitor"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._subscribers = 0
        self._cond = threading.Condition()
        self._latest = ResourceSnapshot(cpu_threads=os.cpu_count() or 8)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._nvidia_path = self._find_nvidia_smi()

    @classmethod
    def get(cls) -> "ResourceMonitor":
        """Get the process-wide singleton."""
        with cls._lock:
            if cls._instance is None:
                inst = cls()
                cls._instance = inst
            return cls._instance

    # ── Subscription lifecycle ────────────────────────────────────────

    def subscribe(self) -> None:
        """Mark the panel as visible. Starts the sampler if not running."""
        with self._cond:
            self._subscribers += 1
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._run, name="ResourceMonitor", daemon=True
                )
                self._thread.start()
        logger.debug("ResourceMonitor subscribed (n=%d)", self._subscribers)

    def unsubscribe(self) -> None:
        """Mark the panel as hidden. Stops the sampler when last consumer leaves."""
        with self._cond:
            if self._subscribers > 0:
                self._subscribers -= 1
            if self._subscribers <= 0:
                self._subscribers = 0
                self._stop.set()
                self._cond.notify_all()
        logger.debug("ResourceMonitor unsubscribed (n=%d)", self._subscribers)

    def stop(self) -> None:
        """Force-stop the sampler. Use only on app shutdown."""
        with self._cond:
            self._stop.set()
            self._subscribers = 0
            self._cond.notify_all()

    def is_active(self) -> bool:
        return self._subscribers > 0

    # ── Read access ───────────────────────────────────────────────────

    def snapshot(self) -> ResourceSnapshot:
        """Read the most recent sample. Returns a copy — safe to mutate."""
        with self._cond:
            return ResourceSnapshot(
                cpu_percent=self._latest.cpu_percent,
                cpu_threads=self._latest.cpu_threads,
                ram_used_gb=self._latest.ram_used_gb,
                ram_total_gb=self._latest.ram_total_gb,
                gpu_percent=self._latest.gpu_percent,
                vram_used_gb=self._latest.vram_used_gb,
                vram_total_gb=self._latest.vram_total_gb,
                timestamp=self._latest.timestamp,
            )

    # ── Sampler thread ────────────────────────────────────────────────

    def _run(self) -> None:
        """Sample once per second while at least one subscriber is active."""
        # Prime psutil's cpu sampling on the first iteration
        if _HAS_PSUTIL:
            try:
                psutil.cpu_percent(interval=None)  # initialize baseline
            except (OSError, ValueError):
                pass
        # 1Hz sampling. We use a cond-wait pattern so unsubscribe+stop
        # returns control immediately, and the thread always sleeps at
        # least 1s between samples (so we don't burn CPU).
        while not self._stop.is_set():
            sample = self._sample_once()
            with self._cond:
                self._latest = sample
                self._cond.notify_all()
            # Sleep, but wake early if we're told to stop
            with self._cond:
                self._cond.wait(timeout=1.0)

    def _sample_once(self) -> ResourceSnapshot:
        snap = ResourceSnapshot(
            cpu_threads=os.cpu_count() or 8,
            timestamp=time.time(),
        )
        if _HAS_PSUTIL:
            try:
                snap.cpu_percent = float(psutil.cpu_percent(interval=None))
            except (OSError, ValueError):
                snap.cpu_percent = 0.0
            try:
                vm = psutil.virtual_memory()
                snap.ram_used_gb = vm.used / (1024 ** 3)
                snap.ram_total_gb = vm.total / (1024 ** 3)
            except (OSError, ValueError):
                pass
        if self._nvidia_path:
            snap.gpu_percent, snap.vram_used_gb, snap.vram_total_gb = (
                self._sample_nvidia()
            )
        return snap

    def _find_nvidia_smi(self) -> Optional[str]:
        """Locate nvidia-smi. Returns path or None."""
        exe = shutil.which("nvidia-smi")
        if exe:
            return exe
        # Common Windows install paths
        candidates = [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def _sample_nvidia(self) -> tuple[int, float, float]:
        """Query nvidia-smi for GPU util + VRAM. Returns (0, 0.0, 0.0) on failure."""
        if not self._nvidia_path:
            return 0, 0.0, 0.0
        try:
            res = subprocess.run(
                [
                    self._nvidia_path,
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return 0, 0.0, 0.0
            line = res.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                return 0, 0.0, 0.0
            gpu = int(parts[0]) if parts[0].isdigit() else 0
            v_used = float(parts[1]) / 1024.0  # MiB → GiB
            v_total = float(parts[2]) / 1024.0
            return gpu, v_used, v_total
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return 0, 0.0, 0.0


def format_resource_line(snap: ResourceSnapshot) -> str:
    """Format a resource line for the status bar / panel."""
    parts = [
        f"CPU {snap.cpu_percent:.0f}%",
        f"RAM {snap.ram_str}",
    ]
    if snap.gpu_percent or snap.vram_total_gb:
        vram = f" VRAM {snap.vram_str}" if snap.vram_total_gb else ""
        parts.append(f"GPU {snap.gpu_percent}%{vram}")
    return " │ ".join(parts)
