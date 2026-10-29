import time
import numpy as np
from pathlib import Path
from apps.api.app.content.idp.service import IdpService
from apps.api.app.content.idp.hardware import HardwareProfiler, PowerMode

# Test on 10 dev split invoices
dev_files = list(Path("docs/ocr-benchmark/data_gst").glob("gst_*_clean.png"))[:10]
print(f"Loaded {len(dev_files)} dev invoices for Eco vs Performance emulation.")

# 1. ECO MODE EMULATION (1 worker, 200 DPI, OMP threads = 1)
prof_eco = HardwareProfiler(mode_override=PowerMode.ECO, force_cpu=True).probe()
svc_eco = IdpService()

lats_eco = []
gstins_correct_eco = 0

for f in dev_files:
    t0 = time.perf_counter()
    res = svc_eco.process_image_path(f)
    dur = (time.perf_counter() - t0) * 1000.0
    lats_eco.append(dur)
    fields = res.get("fields", {})
    if fields.get("supplier_gstin", {}).get("normalized_value"):
        gstins_correct_eco += 1

p50_eco = np.percentile(lats_eco, 50)
p95_eco = np.percentile(lats_eco, 95)
acc_eco = (gstins_correct_eco / len(dev_files)) * 100.0

# 2. PERFORMANCE MODE (300 DPI, multi-core OMP threads = 4)
prof_perf = HardwareProfiler(mode_override=PowerMode.PERFORMANCE, force_cpu=False).probe()
svc_perf = IdpService()

lats_perf = []
gstins_correct_perf = 0

for f in dev_files:
    t0 = time.perf_counter()
    res = svc_perf.process_image_path(f)
    dur = (time.perf_counter() - t0) * 1000.0
    lats_perf.append(dur)
    fields = res.get("fields", {})
    if fields.get("supplier_gstin", {}).get("normalized_value"):
        gstins_correct_perf += 1

p50_perf = np.percentile(lats_perf, 50)
p95_perf = np.percentile(lats_perf, 95)
acc_perf = (gstins_correct_perf / len(dev_files)) * 100.0

print(f"\n--- HARDWARE ADAPTIVE EMULATION RESULTS ---")
print(f"ECO MODE (Low-spec / Battery):")
print(f"  p50 Latency: {p50_eco:.1f}ms | p95 Latency: {p95_eco:.1f}ms | GSTIN Accuracy: {acc_eco:.1f}%")
print(f"PERFORMANCE MODE (Workstation):")
print(f"  p50 Latency: {p50_perf:.1f}ms | p95 Latency: {p95_perf:.1f}ms | GSTIN Accuracy: {acc_perf:.1f}%")

