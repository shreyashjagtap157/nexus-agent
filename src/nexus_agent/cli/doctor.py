"""
Nexus Doctor — Health checks and benchmark runner.

Provides ``nexus doctor`` CLI command with:
- System environment diagnostics (Python, hardware, key packages)
- Cold-start benchmark: time to create and load an LLM provider
- First-token latency benchmark: time to first completion token
- Persistent result history for trend tracking
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Data Types ──────────────────────────────────────────────────────────

REPORT_DIR = Path("~/.nexus-agent/doctor").expanduser()


@dataclass
class HealthMetric:
    """A single measured health metric with metadata."""
    name: str
    value: str | float | int | bool
    unit: str = ""
    status: str = "ok"           # ok | warn | error | info
    ok: bool | None = None       # None = not applicable (info)

    @classmethod
    def ok(cls, name: str, value: Any, unit: str = "") -> HealthMetric:
        return cls(name=name, value=value, unit=unit, status="ok", ok=True)

    @classmethod
    def warn(cls, name: str, value: Any, unit: str = "") -> HealthMetric:
        return cls(name=name, value=value, unit=unit, status="warn", ok=False)

    @classmethod
    def error(cls, name: str, value: Any, unit: str = "") -> HealthMetric:
        return cls(name=name, value=value, unit=unit, status="error", ok=False)

    @classmethod
    def info(cls, name: str, value: Any, unit: str = "") -> HealthMetric:
        return cls(name=name, value=value, unit=unit, status="info", ok=None)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    cold_start_ms: float = 0.0
    first_token_ms: float = 0.0
    model_path: str = ""
    provider: str = ""
    model_name: str = ""
    timestamp: float = field(default_factory=time.time)
    error: str | None = None


@dataclass
class DoctorReport:
    """Complete doctor report."""
    timestamp: float = field(default_factory=time.time)
    system: list[HealthMetric] = field(default_factory=list)
    python_env: list[HealthMetric] = field(default_factory=list)
    key_packages: list[HealthMetric] = field(default_factory=list)
    benchmarks: BenchmarkResult | None = None


# ── Health Check ──────────────────────────────────────────────────────


def _check_package(name: str, min_version: str | None = None) -> HealthMetric:
    """Check whether a Python package is installed and optionally meets a minimum version."""
    try:
        mod = __import__(name.replace("-", "_"))
        ver = getattr(mod, "__version__", None) or getattr(mod, "version", None)
        ver_str = str(ver) if ver else "installed"
        seen_trouble = ver_str in ("installed", "") or "dev" in ver_str
        if min_version and not seen_trouble:
            parts = [int(x) for x in ver_str.split(".") if x.isdigit()]
            min_parts = [int(x) for x in min_version.split(".") if x.isdigit()]
            if parts and min_parts and parts < min_parts:
                return HealthMetric.warn(name, f"{ver_str} (need {min_version})")
        return HealthMetric.ok(name, ver_str)
    except ImportError:
        return HealthMetric.warn(name, "not installed")


def check_system() -> list[HealthMetric]:
    """Check system hardware and OS."""
    metrics: list[HealthMetric] = []
    metrics.append(HealthMetric.info("Platform", f"{platform.system()} {platform.release()}"))
    metrics.append(HealthMetric.info("Architecture", platform.machine()))
    metrics.append(HealthMetric.info("CPU", f"{os.cpu_count() or '?'} cores"))
    metrics.append(HealthMetric.info("Python", platform.python_version()))

    # RAM
    try:
        import psutil
        vm = psutil.virtual_memory()
        total_gb = vm.total / (1024**3)
        avail_gb = vm.available / (1024**3)
        metrics.append(HealthMetric.ok("RAM", f"{avail_gb:.1f}G / {total_gb:.1f}G free", "GB"))
    except ImportError:
        metrics.append(HealthMetric.warn("RAM", "psutil not installed — cannot measure"))

    # Disk for ~/.nexus-agent
    try:
        nexus_dir = Path("~/.nexus-agent").expanduser()
        nexus_dir.mkdir(parents=True, exist_ok=True)
        du = shutil.disk_usage(nexus_dir)
        free_gb = du.free / (1024**3)
        metrics.append(HealthMetric.ok("Disk (data dir)", f"{free_gb:.1f}G free", "GB"))
    except OSError:
        metrics.append(HealthMetric.warn("Disk", "could not check"))

    # GPU
    gpu_info = _detect_gpu()
    if gpu_info:
        metrics.append(HealthMetric.ok("GPU", gpu_info))
    else:
        metrics.append(HealthMetric.ok("GPU", "none detected (CPU-only mode)"))

    # Terminal
    try:
        w, h = shutil.get_terminal_size()
        metrics.append(HealthMetric.info("Terminal", f"{w}x{h}"))
    except (OSError, ValueError):
        pass

    return metrics


def _detect_gpu() -> str | None:
    """Detect GPU capabilities using available libraries."""
    # NVIDIA via nvidia-smi
    try:
        import subprocess
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            if lines:
                parts = [p.strip() for p in lines[0].split(",")]
                name = parts[0]
                vram = parts[1] if len(parts) > 1 else "?"
                return f"{name} ({vram})"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # NVIDIA via pynvml
    try:
        from pynvml import (
            nvmlDeviceGetCount,
            nvmlDeviceGetName,
            nvmlInit,
            nvmlSystemGetDriverVersion,
        )
        nvmlInit()
        count = nvmlDeviceGetCount()
        if count > 0:
            names = []
            for i in range(count):
                name = nvmlDeviceGetName(i)
                names.append(name.decode() if hasattr(name, 'decode') else str(name))
            return ", ".join(names)
    except ImportError:
        pass
    except Exception:
        pass

    # AMD via rocm-smi
    try:
        res = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return "AMD GPU detected"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Apple Silicon Metal
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "Apple Silicon (M-series)"

    # Windows D3D/Vulkan
    if platform.system() == "Windows":
        try:
            res = subprocess.run(
                ["dxdiag", "/t", os.devnull],
                capture_output=True, text=True, timeout=3,
            )
            # dxdiag exists = DirectX available
            if res.returncode == 0 or res.returncode == 1:
                return "DirectX available (GPU likely)"
        except (FileNotFoundError, OSError):
            pass

    return None


def check_python_env() -> list[HealthMetric]:
    """Check Python environment."""
    metrics: list[HealthMetric] = []

    # Key packages for core functionality
    key_pkgs = [
        ("llama-cpp-python", "0.2.0"),
        ("rich", "10.0.0"),
        ("click", "8.0.0"),
    ]
    for pkg, min_ver in key_pkgs:
        metrics.append(_check_package(pkg, min_ver))

    # GPU/acceleration packages
    accel_pkgs = [
        "torch",
        "onnxruntime-genai",
        "keyring",
    ]
    for pkg in accel_pkgs:
        metrics.append(_check_package(pkg))

    return metrics


# ── Benchmark Runner ──────────────────────────────────────────────────


class BenchmarkRunner:
    """Measures cold-start and first-token latency.

    Usage:
        runner = BenchmarkRunner()
        result = runner.run_all(model_path="/path/to/model.gguf")
    """

    def __init__(self) -> None:
        self._cached_provider: Any = None

    def measure_cold_start(
        self,
        model_path: str | None = None,
        provider_name: str = "local",
    ) -> tuple[float, Any]:
        """Measure time to create an LLM provider (cold start).

        Measures the wall-clock time from zero to having a fully loaded
        provider ready for inference. If the provider lazily loads the
        model, the lazy load time is included.

        Returns:
            Tuple of (elapsed_ms, provider_instance).
        """
        from nexus_agent.core.config import load_config
        from nexus_agent.llm.providers.factory import ProviderFactory

        # Clear cache to ensure cold start
        ProviderFactory.clear_cache()

        config = load_config()

        start = time.perf_counter()
        provider = ProviderFactory.create_provider(
            provider_name, config, model_path
        )
        elapsed = (time.perf_counter() - start) * 1000

        return elapsed, provider

    def measure_first_token(
        self,
        provider: Any,
        prompt: str = "Hello",
    ) -> float:
        """Measure time from sending a prompt to receiving the first token.

        Uses streaming if the provider supports it, otherwise uses
        the non-streaming completion time as a proxy.

        Returns:
            Time to first token or completion in milliseconds.
        """
        from nexus_agent.llm.base import Message, Role

        messages = [Message(role=Role.USER, content=prompt)]

        supports_stream = getattr(provider, "supports_streaming", False) or (
            hasattr(provider, "get_capabilities")
            and provider.get_capabilities().supports_streaming
        )

        if supports_stream:
            try:
                start = time.perf_counter()
                first_chunk = True
                for chunk in provider.chat_completion_stream(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=10,
                ):
                    if first_chunk:
                        elapsed = (time.perf_counter() - start) * 1000
                        return elapsed
            except (NotImplementedError, AttributeError, RuntimeError, OSError) as e:
                logger.debug(f"Streaming first-token failed, falling back to sync: {e}")

        # Fallback: measure total sync completion time (proxy for first-token)
        try:
            start = time.perf_counter()
            provider.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
            )
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed
        except (RuntimeError, OSError, ValueError) as e:
            logger.error(f"First-token benchmark failed: {e}")
            return 0.0

    def run_all(
        self,
        model_path: str | None = None,
        provider_name: str = "local",
    ) -> BenchmarkResult:
        """Run both cold-start and first-token benchmarks.

        Args:
            model_path: Path to model file (required for local provider).
            provider_name: Provider name (default: local).

        Returns:
            BenchmarkResult with timings.
        """
        result = BenchmarkResult(
            model_path=model_path or "",
            provider=provider_name,
        )

        # Phase 1: cold start
        try:
            cold_ms, provider = self.measure_cold_start(model_path, provider_name)
            result.cold_start_ms = round(cold_ms, 1)
            if provider:
                result.model_name = getattr(provider, "model_name", "") or ""
        except (RuntimeError, ValueError, OSError, ImportError) as e:
            result.error = f"Cold start failed: {e}"
            logger.warning(f"Cold start benchmark failed: {e}")
            return result

        # Phase 2: first-token latency
        if provider and getattr(provider, "is_loaded", True):
            try:
                ft_ms = self.measure_first_token(provider)
                result.first_token_ms = round(ft_ms, 1)
            except (RuntimeError, ValueError, OSError, TypeError) as e:
                logger.warning(f"First-token benchmark failed: {e}")
                result.first_token_ms = 0.0
        else:
            result.first_token_ms = 0.0
            if not result.error:
                result.error = "Provider did not load"

        return result

    def run_fast(self) -> BenchmarkResult:
        """Run a fast benchmark without model loading (initialization only).

        This measures how fast the Python framework initializes without
        loading an actual model.
        """
        result = BenchmarkResult(
            model_path="(framework only)",
            provider="mock",
        )

        start = time.perf_counter()

        # 1. Import core modules
        import nexus_agent.core.agent
        import nexus_agent.core.config
        import nexus_agent.llm.base
        import nexus_agent.memory.memory_manager
        import nexus_agent.session.manager
        import nexus_agent.tools.base
        nexus_agent.core.config.load_config()

        elapsed = (time.perf_counter() - start) * 1000
        result.cold_start_ms = round(elapsed, 1)
        result.model_name = "(framework init)"

        return result


# ── History Persistence ──────────────────────────────────────────────


def save_benchmark_result(result: BenchmarkResult) -> Path:
    """Save a benchmark result to the doctor report directory."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    path = REPORT_DIR / f"benchmark_{timestamp}.json"
    path.write_text(
        json.dumps(asdict(result), indent=2, default=str),
        encoding="utf-8",
    )
    return path


def load_benchmark_history(limit: int = 20) -> list[BenchmarkResult]:
    """Load recent benchmark results for trend display.

    Args:
        limit: Maximum number of results to load.

    Returns:
        List of BenchmarkResult sorted by timestamp (newest first).
    """
    if not REPORT_DIR.exists():
        return []
    files = sorted(REPORT_DIR.glob("benchmark_*.json"), reverse=True)
    results: list[BenchmarkResult] = []
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(BenchmarkResult(**data))
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.debug(f"Skipping corrupt benchmark file {f.name}: {e}")
    return results


# ── Print Helpers (Rich) ─────────────────────────────────────────────


def print_report(report: DoctorReport) -> None:
    """Pretty-print a full doctor report using rich."""
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    console.print()
    console.print(Panel.fit("[bold]🩺 Nexus Doctor — Full Diagnostic Report[/bold]", border_style="cyan"))
    console.print()

    # ── System ──
    sys_table = Table(title="System", box=box.SIMPLE, title_style="bold cyan", show_header=False)
    sys_table.add_column("Metric", style="cyan", width=22)
    sys_table.add_column("Value", style="white")
    sys_table.add_column("Status", width=8)
    for m in report.system:
        status_icon = _status_icon(m)
        sys_table.add_row(m.name, str(m.value) + (f" {m.unit}" if m.unit else ""), status_icon)
    console.print(sys_table)
    console.print()

    # ── Python Env ──
    py_table = Table(title="Python Environment", box=box.SIMPLE, title_style="bold cyan", show_header=False)
    py_table.add_column("Package", style="cyan", width=22)
    py_table.add_column("Version", style="white")
    py_table.add_column("Status", width=8)
    for m in report.python_env:
        status_icon = _status_icon(m)
        py_table.add_row(m.name, str(m.value), status_icon)
    console.print(py_table)
    console.print()

    # ── Benchmarks ──
    bench = report.benchmarks
    if bench:
        bm_table = Table(title="Benchmarks", box=box.SIMPLE, title_style="bold cyan", show_header=False)
        bm_table.add_column("Metric", style="cyan", width=22)
        bm_table.add_column("Value", style="white")
        bm_table.add_column("Status", width=8)
        bm_table.add_row("Provider", bench.provider)
        bm_table.add_row("Model", bench.model_name or bench.model_path or "(none)")
        if bench.error:
            bm_table.add_row("Error", f"[red]{bench.error}[/red]", "❌")
        else:
            cold_icon = _bench_status(bench.cold_start_ms, 10000, 30000)
            ft_icon = _bench_status(bench.first_token_ms, 500, 2000)
            bm_table.add_row(
                "Cold start",
                f"{bench.cold_start_ms:,.0f} ms" if bench.cold_start_ms > 0 else "N/A",
                cold_icon,
            )
            bm_table.add_row(
                "First token",
                f"{bench.first_token_ms:,.0f} ms" if bench.first_token_ms > 0 else "N/A",
                ft_icon,
            )
        console.print(bm_table)
        console.print()

    # ── History ──
    history = load_benchmark_history(limit=3)
    if history:
        hist_table = Table(title="Recent Benchmarks", box=box.SIMPLE, title_style="bold cyan")
        hist_table.add_column("Date", style="dim", width=12)
        hist_table.add_column("Model", style="cyan", width=20)
        hist_table.add_column("Cold Start", justify="right", width=12)
        hist_table.add_column("First Token", justify="right", width=12)
        hist_table.add_column("Error", style="red", width=20)
        for h in history[:3]:
            date_str = time.strftime("%m-%d %H:%M", time.localtime(h.timestamp))
            model_str = (h.model_name or Path(h.model_path).name if h.model_path else "?")[:20]
            err_str = (h.error or "")[:20]
            hist_table.add_row(
                date_str,
                model_str,
                f"{h.cold_start_ms:,.0f}ms" if h.cold_start_ms > 0 else "—",
                f"{h.first_token_ms:,.0f}ms" if h.first_token_ms > 0 else "—",
                err_str,
            )
        console.print(hist_table)
        console.print()

    console.print("[dim]To re-run with a model: nexus doctor --model path/to/model.gguf[/dim]")
    console.print()


def _status_icon(m: HealthMetric) -> str:
    if m.status == "ok":
        return "[green]✓[/green]"
    elif m.status == "warn":
        return "[yellow]⚠[/yellow]"
    elif m.status == "error":
        return "[red]✗[/red]"
    return "[dim]ℹ[/dim]"


def _bench_status(ms: float, good_threshold: float, warn_threshold: float) -> str:
    if ms <= 0:
        return "[dim]—[/dim]"
    if ms <= good_threshold:
        return "[green]✓ fast[/green]"
    elif ms <= warn_threshold:
        return "[yellow]⚠ moderate[/yellow]"
    return "[red]✗ slow[/red]"


# ── Main Entry Point ─────────────────────────────────────────────────


def run_doctor(
    model_path: str | None = None,
    provider: str = "local",
    run_benchmarks: bool = True,
) -> DoctorReport:
    """Run all health checks and optionally benchmarks.

    Args:
        model_path: Path to a GGUF model for benchmarking.
        provider: Provider name (default: local).
        run_benchmarks: Whether to run benchmarks.

    Returns:
        DoctorReport with all results.
    """
    report = DoctorReport()
    report.system = check_system()
    report.python_env = check_python_env()

    if run_benchmarks:
        runner = BenchmarkRunner()

        # First run the fast framework-only benchmark (always works)
        fast_result = runner.run_fast()
        report.benchmarks = fast_result

        # If a model was provided, run the full benchmark
        if model_path:
            model_path_resolved = str(Path(model_path).resolve())
            if not Path(model_path_resolved).exists():
                logger.warning(f"Model path does not exist: {model_path_resolved}")
                fast_result.error = fast_result.error or f"Model not found: {model_path_resolved}"
            else:
                full_result = runner.run_all(model_path_resolved, provider)
                report.benchmarks = full_result
                save_benchmark_result(full_result)

    return report
