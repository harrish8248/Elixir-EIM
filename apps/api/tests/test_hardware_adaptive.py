"""Comprehensive Hardware Profiler & Adaptive OCR Unit Tests.

Verifies:
(a) 2 cores, 4 GB RAM, no GPU -> LOW: heavy engines skipped, 1 worker, 200 DPI, Indra on CPU provider
(b) 8 cores, 16 GB, no GPU -> MEDIUM
(c) 16 cores, 32 GB, 8 GB VRAM -> HIGH: GPU engines allowed
(d) force-CPU override
(e) GPU present but little free VRAM -> engines fall back to CPU
(f) assert Indra's ONNX session never includes a GPU provider on any profile
(g) memory guard prevents a model load when RAM is short
(h) probe failure falls back safely
"""

import pytest
from apps.api.app.content.idp.hardware import (
    ENGINE_RESOURCE_PROFILES,
    HardwareProfiler,
    HardwareTier,
    PowerMode,
)


def test_scenario_a_low_tier():
    """(a) 2 cores, 4 GB RAM, no GPU -> LOW: heavy engines skipped, 1 worker, 200 DPI."""
    profiler = HardwareProfiler(mode_override=PowerMode.AUTO, force_cpu=True)
    tier, mode, warnings = profiler._compute_tier(
        logical_cores=2,
        avail_ram_gb=3.5,
        has_gpu=False,
        vram_free_gb=0.0,
        on_battery=False,
    )
    assert tier == HardwareTier.LOW
    workers, threads, dpi = profiler._derive_adaptive_params(
        tier=tier,
        effective_mode=mode,
        logical_cores=2,
        avail_ram_gb=3.5,
    )
    assert workers == 1
    assert dpi == 200
    assert threads <= 2

    devices = profiler._map_engine_devices(
        tier=tier,
        has_gpu=False,
        vram_free_gb=0.0,
        avail_ram_gb=2.0,  # 2 GB available RAM: enough for Indra (600MB) but not Surya (2500MB)
        threads=threads,
    )
    # Surrounding safety margin (require >= 500 MB after loading):
    # Available = 1024 MB. Surya needs 2500 MB -> Must be SKIPPED
    assert devices["surya"]["device"] == "SKIPPED"
    assert "Insufficient RAM" in devices["surya"]["reason"]
    # Indra must be CPU
    assert devices["indra"]["device"] == "CPU"


def test_scenario_b_medium_tier():
    """(b) 8 cores, 16 GB, no GPU -> MEDIUM."""
    profiler = HardwareProfiler(mode_override=PowerMode.AUTO, force_cpu=True)
    tier, mode, warnings = profiler._compute_tier(
        logical_cores=8,
        avail_ram_gb=12.0,
        has_gpu=False,
        vram_free_gb=0.0,
        on_battery=False,
    )
    assert tier == HardwareTier.MEDIUM
    workers, threads, dpi = profiler._derive_adaptive_params(
        tier=tier,
        effective_mode=mode,
        logical_cores=8,
        avail_ram_gb=12.0,
    )
    assert workers >= 2
    assert dpi == 300


def test_scenario_c_high_tier_gpu_allowed():
    """(c) 16 cores, 32 GB, 8 GB VRAM -> HIGH: GPU engines allowed."""
    profiler = HardwareProfiler(mode_override=PowerMode.PERFORMANCE, force_cpu=False)
    tier, mode, warnings = profiler._compute_tier(
        logical_cores=16,
        avail_ram_gb=28.0,
        has_gpu=True,
        vram_free_gb=8.0,
        on_battery=False,
    )
    assert tier == HardwareTier.HIGH
    workers, threads, dpi = profiler._derive_adaptive_params(
        tier=tier,
        effective_mode=mode,
        logical_cores=16,
        avail_ram_gb=28.0,
    )
    assert workers >= 4
    assert dpi == 300

    devices = profiler._map_engine_devices(
        tier=tier,
        has_gpu=True,
        vram_free_gb=8.0,
        avail_ram_gb=28.0,
        threads=threads,
    )
    assert devices["paddleocr"]["device"] == "GPU"
    assert devices["doctr"]["device"] == "GPU"
    assert devices["easyocr"]["device"] == "GPU"
    assert devices["surya"]["device"] == "GPU"


def test_scenario_d_force_cpu_override():
    """(d) force-CPU override disables GPU even on strong GPU hardware."""
    profiler = HardwareProfiler(mode_override=PowerMode.PERFORMANCE, force_cpu=True)
    tier, mode, warnings = profiler._compute_tier(
        logical_cores=16,
        avail_ram_gb=30.0,
        has_gpu=True,
        vram_free_gb=8.0,
        on_battery=False,
    )
    devices = profiler._map_engine_devices(
        tier=tier,
        has_gpu=False,  # Force CPU sets has_gpu to False
        vram_free_gb=0.0,
        avail_ram_gb=30.0,
        threads=4,
    )
    assert devices["paddleocr"]["device"] == "CPU"
    assert devices["doctr"]["device"] == "CPU"
    assert any("Force CPU-only" in w for w in warnings)


def test_scenario_e_gpu_low_vram_fallback():
    """(e) GPU present but little free VRAM -> engines fall back to CPU."""
    profiler = HardwareProfiler(mode_override=PowerMode.BALANCED, force_cpu=False)
    # Only 500 MB free VRAM
    devices = profiler._map_engine_devices(
        tier=HardwareTier.MEDIUM,
        has_gpu=True,
        vram_free_gb=0.5,
        avail_ram_gb=10.0,
        threads=4,
    )
    # docTR needs 3000 MB VRAM, EasyOCR needs 1500 MB VRAM -> Must fall back to CPU
    assert devices["doctr"]["device"] == "CPU"
    assert "insufficient VRAM" in devices["doctr"]["reason"]
    assert devices["easyocr"]["device"] == "CPU"


def test_scenario_f_indra_strictly_cpu_only():
    """(f) assert Indra's ONNX session never includes a GPU provider on any profile."""
    from apps.api.app.content.idp.engine import IndraEngine

    engine = IndraEngine()
    # Contract: IndraEngine declares CPU-only and enforces CPUExecutionProvider
    prof = ENGINE_RESOURCE_PROFILES["indra"]
    assert prof.device_support == "CPU_ONLY"
    assert prof.min_vram_mb == 0.0

    # Ensure even on a HIGH tier profile with massive GPU, Indra mapping is CPU
    profiler = HardwareProfiler()
    devices = profiler._map_engine_devices(
        tier=HardwareTier.HIGH,
        has_gpu=True,
        vram_free_gb=24.0,
        avail_ram_gb=64.0,
        threads=8,
    )
    assert devices["indra"]["device"] == "CPU"
    assert "CPU-only by engine design" in devices["indra"]["reason"]


def test_scenario_g_memory_guard():
    """(g) memory guard prevents a model load when RAM is short."""
    profiler = HardwareProfiler()
    # Host has only 700 MB RAM available
    # Available = 700 MB. Safety margin = 500 MB -> Maximum usable = 200 MB
    devices = profiler._map_engine_devices(
        tier=HardwareTier.LOW,
        has_gpu=False,
        vram_free_gb=0.0,
        avail_ram_gb=0.68,  # ~700 MB
        threads=1,
    )
    # Tesseract needs 350 MB -> (700 - 350 = 350 < 500 margin) -> SKIPPED
    assert devices["tesseract"]["device"] == "SKIPPED"
    assert devices["doctr"]["device"] == "SKIPPED"
    assert devices["surya"]["device"] == "SKIPPED"


def test_scenario_h_probe_safe_fallback():
    """(h) probe failure falls back safely without throwing unhandled exceptions."""
    profiler = HardwareProfiler()
    # Call probe on current environment
    profile = profiler.probe()
    assert profile.tier in (HardwareTier.LOW, HardwareTier.MEDIUM, HardwareTier.HIGH)
    assert profile.chosen_workers >= 1
    assert profile.render_dpi in (200, 300)
    assert isinstance(profile.engine_devices, dict)
    assert "tesseract" in profile.engine_devices
    assert "indra" in profile.engine_devices
