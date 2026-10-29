"""Hardware Profiler, Adaptive Resource Tiering, and Engine Resource Profiles.

Ensures Elixir EIM adapts automatically to any host environment:
- Low-end laptops (CPU-only, 4-8 GB RAM): lightweight passes, 200 DPI, conservative thread pools
- High-end workstations with GPUs: parallel workers, 300 DPI, neural secondary passes
- Strict privacy: Never reads or logs document content.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
from typing import Any

import psutil

from apps.api.app.platform.logging import logger

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class HardwareTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PowerMode(str, Enum):
    AUTO = "AUTO"
    ECO = "ECO"
    BALANCED = "BALANCED"
    PERFORMANCE = "PERFORMANCE"


@dataclass
class EngineResourceProfile:
    engine_id: str
    device_support: str  # "CPU_ONLY" | "CPU_GPU"
    min_ram_mb: float
    typical_ram_mb: float
    min_vram_mb: float = 0.0
    disk_size_mb: float = 0.0
    model_load_time_sec: float = 0.5
    default_threads: int = 2


ENGINE_RESOURCE_PROFILES: dict[str, EngineResourceProfile] = {
    "pymupdf": EngineResourceProfile(
        engine_id="pymupdf",
        device_support="CPU_ONLY",
        min_ram_mb=100.0,
        typical_ram_mb=200.0,
        min_vram_mb=0.0,
        disk_size_mb=104.0,
        model_load_time_sec=0.1,
        default_threads=1,
    ),
    "tesseract": EngineResourceProfile(
        engine_id="tesseract",
        device_support="CPU_ONLY",
        min_ram_mb=150.0,
        typical_ram_mb=350.0,
        min_vram_mb=0.0,
        disk_size_mb=40.0,
        model_load_time_sec=0.2,
        default_threads=2,
    ),
    "indra": EngineResourceProfile(
        engine_id="indra",
        device_support="CPU_ONLY",  # Explicitly CPU-only by architectural contract
        min_ram_mb=300.0,
        typical_ram_mb=600.0,
        min_vram_mb=0.0,
        disk_size_mb=120.0,
        model_load_time_sec=0.8,
        default_threads=2,
    ),
    "paddleocr": EngineResourceProfile(
        engine_id="paddleocr",
        device_support="CPU_GPU",
        min_ram_mb=800.0,
        typical_ram_mb=1500.0,
        min_vram_mb=2048.0,
        disk_size_mb=450.0,
        model_load_time_sec=2.5,
        default_threads=4,
    ),
    "doctr": EngineResourceProfile(
        engine_id="doctr",
        device_support="CPU_GPU",
        min_ram_mb=1000.0,
        typical_ram_mb=2000.0,
        min_vram_mb=3000.0,
        disk_size_mb=600.0,
        model_load_time_sec=3.0,
        default_threads=4,
    ),
    "easyocr": EngineResourceProfile(
        engine_id="easyocr",
        device_support="CPU_GPU",
        min_ram_mb=600.0,
        typical_ram_mb=1200.0,
        min_vram_mb=1500.0,
        disk_size_mb=300.0,
        model_load_time_sec=1.8,
        default_threads=2,
    ),
    "surya": EngineResourceProfile(
        engine_id="surya",
        device_support="CPU_GPU",
        min_ram_mb=1200.0,
        typical_ram_mb=2500.0,
        min_vram_mb=4000.0,
        disk_size_mb=800.0,
        model_load_time_sec=3.5,
        default_threads=4,
    ),
}


@dataclass
class HardwareProfile:
    os_name: str
    os_version: str
    cpu_model: str
    physical_cores: int
    logical_cores: int
    cpu_load_percent: float
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float
    has_gpu: bool
    gpu_name: str | None
    vram_total_gb: float
    vram_free_gb: float
    on_battery: bool
    onnx_providers: list[str]
    tier: HardwareTier
    effective_mode: PowerMode
    chosen_workers: int
    chosen_threads: int
    render_dpi: int
    engine_devices: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class HardwareProfiler:
    """Probes system hardware resources safely and computes adaptive execution policies."""

    def __init__(self, mode_override: PowerMode = PowerMode.AUTO, force_cpu: bool = False):
        self.mode_override = mode_override
        self.force_cpu = force_cpu

    def probe(self) -> HardwareProfile:
        """Probe real machine hardware without risk of crashing."""
        os_name = platform.system()
        os_version = f"{platform.release()} ({platform.machine()})"

        # CPU info
        cpu_model = platform.processor() or "Generic x86_64"
        phys_cores = psutil.cpu_count(logical=False) or 2
        logical_cores = psutil.cpu_count(logical=True) or phys_cores
        cpu_load = psutil.cpu_percent(interval=None)

        # RAM info
        mem = psutil.virtual_memory()
        total_ram_gb = round(mem.total / (1024**3), 2)
        avail_ram_gb = round(mem.available / (1024**3), 2)

        # Disk space for models / caches
        model_dir = Path(os.environ.get("ELIXIR_MODELS_DIR", "."))
        try:
            free_disk_gb = round(shutil.disk_usage(model_dir).free / (1024**3), 2)
        except Exception:
            free_disk_gb = 10.0

        # Battery check
        on_battery = False
        try:
            batt = psutil.sensors_battery()
            if batt and not batt.power_plugged:
                on_battery = True
        except Exception:
            pass

        # ONNX Providers
        onnx_providers = ort.get_available_providers() if ort else ["CPUExecutionProvider"]

        # GPU probe (NVIDIA via nvidia-smi or DirectML / CUDA providers)
        has_gpu = False
        gpu_name = None
        vram_total_gb = 0.0
        vram_free_gb = 0.0

        if not self.force_cpu:
            has_gpu, gpu_name, vram_total_gb, vram_free_gb = self._probe_gpu(onnx_providers)

        # Compute tier
        tier, effective_mode, warnings = self._compute_tier(
            logical_cores=logical_cores,
            avail_ram_gb=avail_ram_gb,
            has_gpu=has_gpu,
            vram_free_gb=vram_free_gb,
            on_battery=on_battery,
        )

        # Compute adaptive parameters
        workers, threads, render_dpi = self._derive_adaptive_params(
            tier=tier,
            effective_mode=effective_mode,
            logical_cores=logical_cores,
            avail_ram_gb=avail_ram_gb,
        )

        # Engine device mapping & load feasibility
        engine_devices = self._map_engine_devices(
            tier=tier,
            has_gpu=has_gpu,
            vram_free_gb=vram_free_gb,
            avail_ram_gb=avail_ram_gb,
            threads=threads,
        )

        return HardwareProfile(
            os_name=os_name,
            os_version=os_version,
            cpu_model=cpu_model,
            physical_cores=phys_cores,
            logical_cores=logical_cores,
            cpu_load_percent=cpu_load,
            total_ram_gb=total_ram_gb,
            available_ram_gb=avail_ram_gb,
            free_disk_gb=free_disk_gb,
            has_gpu=has_gpu,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_free_gb=vram_free_gb,
            on_battery=on_battery,
            onnx_providers=onnx_providers,
            tier=tier,
            effective_mode=effective_mode,
            chosen_workers=workers,
            chosen_threads=threads,
            render_dpi=render_dpi,
            engine_devices=engine_devices,
            warnings=warnings,
        )

    def _probe_gpu(self, onnx_providers: list[str]) -> tuple[bool, str | None, float, float]:
        """Query GPU presence safely via nvidia-smi with fallback to DirectML."""
        if shutil.which("nvidia-smi"):
            try:
                cmd = ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"]
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
                if out.returncode == 0 and out.stdout.strip():
                    parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
                    name = parts[0]
                    tot_vram = round(float(parts[1]) / 1024.0, 2)
                    free_vram = round(float(parts[2]) / 1024.0, 2)
                    return True, name, tot_vram, free_vram
            except Exception as e:
                logger.debug(f"nvidia-smi probe bypassed: {e}")

        # Check for DirectML execution provider on Windows
        if "DmlExecutionProvider" in onnx_providers:
            return True, "DirectML Accelerator", 4.0, 3.0

        return False, None, 0.0, 0.0

    def _compute_tier(
        self,
        logical_cores: int,
        avail_ram_gb: float,
        has_gpu: bool,
        vram_free_gb: float,
        on_battery: bool,
    ) -> tuple[HardwareTier, PowerMode, list[str]]:
        warnings = []
        mode = self.mode_override

        if mode == PowerMode.AUTO:
            effective_mode = PowerMode.ECO if on_battery else PowerMode.BALANCED
        else:
            effective_mode = mode

        if on_battery and effective_mode != PowerMode.PERFORMANCE:
            warnings.append("System is running on battery power: Eco energy-saving policy active")

        # Determine Tier based on hardware constraints
        if self.force_cpu:
            warnings.append("Force CPU-only override active: all GPU acceleration disabled")
            has_gpu = False

        if effective_mode == PowerMode.ECO:
            tier = HardwareTier.LOW
        elif (has_gpu and vram_free_gb >= 6.0) or (logical_cores >= 12 and avail_ram_gb >= 16.0):
            tier = HardwareTier.HIGH
        elif (logical_cores >= 6 and avail_ram_gb >= 6.0) or (has_gpu and vram_free_gb >= 2.0):
            tier = HardwareTier.MEDIUM
        else:
            tier = HardwareTier.LOW

        if avail_ram_gb < 4.0:
            warnings.append(f"Low available RAM ({avail_ram_gb:.1f} GB): heavy neural models deferred to on-demand")

        return tier, effective_mode, warnings

    def _derive_adaptive_params(
        self,
        tier: HardwareTier,
        effective_mode: PowerMode,
        logical_cores: int,
        avail_ram_gb: float,
    ) -> tuple[int, int, int]:
        """Derive workers, threads, and render DPI."""
        if tier == HardwareTier.LOW or effective_mode == PowerMode.ECO:
            workers = 1
            threads = min(2, logical_cores)
            render_dpi = 200
        elif tier == HardwareTier.MEDIUM:
            workers = max(1, min(logical_cores - 1, int(avail_ram_gb // 3), 4))
            threads = min(4, logical_cores)
            render_dpi = 300
        else:  # HIGH
            workers = max(2, min(logical_cores - 2, int(avail_ram_gb // 2), 8))
            threads = min(8, logical_cores)
            render_dpi = 300

        # Set environment variable for C-libraries (Tesseract/OpenMP)
        os.environ["OMP_THREAD_LIMIT"] = str(threads)
        return workers, threads, render_dpi

    def _map_engine_devices(
        self,
        tier: HardwareTier,
        has_gpu: bool,
        vram_free_gb: float,
        avail_ram_gb: float,
        threads: int,
    ) -> dict[str, dict[str, Any]]:
        """Map which device each engine will use and check memory safety margins."""
        mapping = {}
        avail_ram_mb = avail_ram_gb * 1024.0
        vram_free_mb = vram_free_gb * 1024.0

        for eng_id, prof in ENGINE_RESOURCE_PROFILES.items():
            # Check safety margin (require at least 500 MB left after loading)
            can_load = (avail_ram_mb - prof.typical_ram_mb) >= 500.0

            if not can_load:
                device = "SKIPPED"
                reason = f"Insufficient RAM: needs {prof.typical_ram_mb:.0f}MB, available {avail_ram_mb:.0f}MB"
            elif prof.device_support == "CPU_ONLY":
                device = "CPU"
                reason = "CPU-only by engine design"
            elif has_gpu and not self.force_cpu and (vram_free_mb >= prof.min_vram_mb) and tier != HardwareTier.LOW:
                device = "GPU"
                reason = f"Accelerated via GPU ({prof.min_vram_mb:.0f}MB VRAM assigned)"
            else:
                device = "CPU"
                reason = "CPU fallback (insufficient VRAM or LOW tier)" if has_gpu else "CPU execution"

            mapping[eng_id] = {
                "device": device,
                "reason": reason,
                "ram_mb": prof.typical_ram_mb,
                "vram_mb": prof.min_vram_mb if device == "GPU" else 0.0,
                "disk_mb": prof.disk_size_mb,
                "threads": min(threads, prof.default_threads),
                "is_active": device != "SKIPPED",
            }
        return mapping
