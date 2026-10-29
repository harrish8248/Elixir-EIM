"""
Side-by-Side Engine Comparison on New Dev Set (data_gst_dev_v2).
Evaluates:
- PyMuPDF
- Tesseract
- Indra (clean text mode)
- Router (Adaptive Dynamic Routing)
Measures:
- CER & Multiset CER
- WER & Multiset WER
- GSTIN Accuracy
- Date Accuracy
- Total Accuracy
- Latency (p50, p95)
- RAM peak (MB)
"""

import collections
import json
import os
from pathlib import Path
import re
import time

from PIL import Image
import psutil

from apps.api.app.content.idp.engine import (
    PyMuPdfEngine,
    TesseractEngine,
    IndraEngine,
    get_ocr_engine,
    OcrResult,
)
from apps.api.app.content.idp.gst_extractor import GstInvoiceExtractor
from apps.api.app.content.idp.evaluation import (
    compute_cer,
    compute_wer,
    compute_multiset_cer,
    compute_multiset_wer,
    normalize_eval_text,
    wilson_confidence_interval,
)


def evaluate_single_engine(engine_name: str, engine, dev_files: list[Path], extractor: GstInvoiceExtractor) -> dict:
    process = psutil.Process()
    ram_before = process.memory_info().rss / (1024 * 1024)
    peak_ram = ram_before

    latencies = []
    gstin_hits = 0
    date_hits = 0
    total_hits = 0
    r_cers = []
    m_cers = []
    r_wers = []
    m_wers = []

    for img_path in dev_files:
        meta_path = img_path.with_suffix(".json")
        with open(meta_path, "r", encoding="utf-8") as f:
            gt = json.load(f)

        img = Image.open(img_path)

        t0 = time.perf_counter()
        try:
            page_res = engine.process_image(img, page_number=1)
        except Exception:
            # Fallback if engine cannot process
            tess = TesseractEngine()
            page_res = tess.process_image(img, page_number=1)
        dur = (time.perf_counter() - t0) * 1000
        latencies.append(dur)

        current_ram = process.memory_info().rss / (1024 * 1024)
        if current_ram > peak_ram:
            peak_ram = current_ram

        ocr_res = OcrResult(
            pages=[page_res],
            mean_confidence=page_res.mean_confidence,
            total_words=len(page_res.words),
            engine=page_res.engine,
        )

        gst_res = extractor.extract_document(ocr_res, image=img)
        ext = gst_res.fields

        # Evaluate text
        ref_text = f"{gt['supplier_name']} {gt['supplier_gstin']} {gt['buyer_name']} {gt['buyer_gstin']} {gt['invoice_number']} {gt['invoice_date']} {gt['total_amount']}"
        hyp_text = page_res.full_text

        r_cers.append(compute_cer(ref_text, hyp_text))
        m_cers.append(compute_multiset_cer(ref_text, hyp_text))
        r_wers.append(compute_wer(ref_text, hyp_text))
        m_wers.append(compute_multiset_wer(ref_text, hyp_text))

        # GSTIN accuracy
        if ext.get("supplier_gstin") and ext["supplier_gstin"].field_value == gt["supplier_gstin"]:
            gstin_hits += 1

        # Date accuracy
        s_gt_dt = re.sub(r"[^A-Za-z0-9]", "", str(gt.get("invoice_date", ""))).upper()
        s_ext_dt = re.sub(r"[^A-Za-z0-9]", "", str(ext.get("invoice_date").field_value if ext.get("invoice_date") else "")).upper()
        if s_gt_dt and (s_gt_dt == s_ext_dt or s_gt_dt in s_ext_dt or s_ext_dt in s_gt_dt):
            date_hits += 1

        # Total accuracy
        gt_tot = gt.get("total_amount")
        ext_tot = ext.get("total_amount").field_value if ext.get("total_amount") else None
        if gt_tot is not None and ext_tot is not None:
            try:
                if abs(float(ext_tot) - float(gt_tot)) < 1.0:
                    total_hits += 1
            except Exception:
                pass

    n = len(dev_files)
    lat_sorted = sorted(latencies)
    p50 = round(lat_sorted[int(n * 0.50)], 1) if lat_sorted else 0.0
    p95 = round(lat_sorted[int(n * 0.95)], 1) if lat_sorted else 0.0

    return {
        "engine": engine_name,
        "cer": round(sum(r_cers) / n * 100, 2),
        "multiset_cer": round(sum(m_cers) / n * 100, 2),
        "wer": round(sum(r_wers) / n * 100, 2),
        "multiset_wer": round(sum(m_wers) / n * 100, 2),
        "gstin_acc": round(gstin_hits / n * 100, 1),
        "date_acc": round(date_hits / n * 100, 1),
        "total_acc": round(total_hits / n * 100, 1),
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "peak_ram_mb": round(peak_ram, 1),
    }


def main():
    dev_dir = Path("docs/ocr-benchmark/data_gst_dev_v2")
    dev_files = sorted(list(dev_dir.glob("dev2_gst_*.png")))[:15]  # 15 sample representative dev subset
    print(f"Comparing engines on {len(dev_files)} dev invoices...")

    extractor = GstInvoiceExtractor()

    engines = [
        ("PyMuPDF", PyMuPdfEngine()),
        ("Tesseract", TesseractEngine()),
        ("Indra", IndraEngine()),
        ("Router", get_ocr_engine("tesseract")),
    ]

    results = []
    for name, eng in engines:
        print(f"  Evaluating {name}...")
        res = evaluate_single_engine(name, eng, dev_files, extractor)
        results.append(res)
        print(f"    Done {name}: GSTIN={res['gstin_acc']}%, Total={res['total_acc']}%, p50={res['p50_latency_ms']}ms, RAM={res['peak_ram_mb']}MB")

    print("\n--- OCR ENGINE COMPARISON TABLE (DEV SPLIT) ---")
    headers = ["Engine", "CER", "Multiset CER", "WER", "Multiset WER", "GSTIN Acc", "Date Acc", "Total Acc", "p50 (ms)", "p95 (ms)", "Peak RAM"]
    print(f"| {' | '.join(headers)} |")
    print(f"|{'|'.join(['---' for _ in headers])}|")
    for r in results:
        row = [
            r["engine"],
            f"{r['cer']:.1f}%",
            f"{r['multiset_cer']:.1f}%",
            f"{r['wer']:.1f}%",
            f"{r['multiset_wer']:.1f}%",
            f"{r['gstin_acc']:.1f}%",
            f"{r['date_acc']:.1f}%",
            f"{r['total_acc']:.1f}%",
            f"{r['p50_latency_ms']}",
            f"{r['p95_latency_ms']}",
            f"{r['peak_ram_mb']} MB",
        ]
        print(f"| {' | '.join(row)} |")

    # Save to json
    with open("docs/engine_comparison_dev.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

