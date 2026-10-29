"""Evaluation Harness for Indian GST Invoices.

Measures:
- Supplier & Buyer GSTIN Exact Match, Checksum Validity, and OCR Confusion Repair Rate
- Field-level Exact Match (Invoice Number, Date, Place of Supply, Bank Details)
- Monetary Totals & Mathematical Tax Reconciliation (Intra-state CGST+SGST vs Inter-state IGST)
- Offline E-Invoice QR Code Detection & Cross-validation
- True Visual Bounding Box IoU (IoU >= 0.5, IoU >= 0.7, Mean IoU)
- Clean vs Degraded Document Breakdown
- Latency (p50, p95)
"""

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any
import numpy as np

from apps.api.app.content.idp.engine import TesseractEngine, get_ocr_engine
from apps.api.app.content.idp.gst_extractor import GstInvoiceExtractor
from apps.api.app.content.idp.gstin import calculate_iou, validate_gstin


def evaluate_gst_dataset(
    split: str = "test",
    engine_name: str = "tesseract",
    data_dir: str = "docs/ocr-benchmark/data_gst",
    splits_file: str = "docs/ocr-benchmark/data_gst/splits_gst.json",
) -> dict[str, Any]:
    print(f"\n================================================================================")
    print(f"  RUNNING INDIAN GST IDP EVALUATION: Split='{split}', Engine='{engine_name}'")
    print(f"================================================================================")

    data_path = Path(data_dir)
    splits_path = Path(splits_file)
    if not splits_path.exists():
        raise FileNotFoundError(f"Splits file not found: {splits_path}")

    with open(splits_path, "r", encoding="utf-8") as f:
        all_splits = json.load(f)

    doc_ids = all_splits.get(split, [])
    if not doc_ids:
        raise ValueError(f"No documents found for split '{split}'")

    print(f"Evaluating {len(doc_ids)} documents in '{split}' split...")

    # Initialize OCR Engine and Extractor
    ocr_engine = TesseractEngine(
        enable_osd=True,
        enable_deskew=True,
        enable_clahe=True,
        enable_denoise=True,
        enable_multipass=True,
    ) if engine_name == "tesseract" else get_ocr_engine(engine_name)

    extractor = GstInvoiceExtractor()

    records = []
    latencies = []

    # Per-field tracking
    fields_to_track = [
        "supplier_gstin", "buyer_gstin", "invoice_number", "invoice_date",
        "place_of_supply", "taxable_value", "cgst", "sgst", "igst",
        "total_amount", "bank_ifsc", "bank_account",
    ]

    field_matches: dict[str, list[bool]] = {f: [] for f in fields_to_track}
    field_ious: dict[str, list[float]] = {f: [] for f in fields_to_track}
    ious_ge_05: list[bool] = []
    ious_ge_07: list[bool] = []

    gstin_checksum_valid = []
    gstin_repairs_count = 0
    math_reconciled = []
    qr_decoded = []

    clean_records = []
    deg_records = []

    for idx, doc_id in enumerate(doc_ids):
        json_file = data_path / f"{doc_id}.json"
        png_file = data_path / f"{doc_id}.png"

        if not json_file.exists() or not png_file.exists():
            print(f"Warning: Missing files for {doc_id}, skipping")
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            gt = json.load(f)

        t0 = time.perf_counter()
        ocr_result = ocr_engine.process_document(png_file.read_bytes(), png_file.name, "image/png")
        extraction = extractor.extract_document(ocr_result, image=str(png_file), ground_truth=gt)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        is_deg = gt.get("is_degraded", False)

        # Field exact match check
        doc_field_matches = {}
        for fname in fields_to_track:
            gt_val = gt.get(fname)
            ext_field = extraction.fields.get(fname)
            pred_val = ext_field.field_value if ext_field else None

            is_match = False
            if gt_val is None and pred_val is None:
                is_match = True
            elif gt_val is not None and pred_val is not None:
                if isinstance(gt_val, (int, float)) and isinstance(pred_val, (int, float)):
                    is_match = abs(float(gt_val) - float(pred_val)) <= 1.0  # 1 INR tolerance
                elif fname == "place_of_supply":
                    # Check substring match (e.g. Maharashtra or 27)
                    clean_gt = str(gt_val).lower()
                    clean_pred = str(pred_val).lower()
                    is_match = (clean_gt in clean_pred) or (clean_pred in clean_gt)
                else:
                    is_match = (str(gt_val).strip().upper() == str(pred_val).strip().upper())

            field_matches[fname].append(is_match)
            doc_field_matches[fname] = is_match

            # IoU tracking
            iou = extraction.iou_scores.get(fname, 0.0)
            field_ious[fname].append(iou)
            ious_ge_05.append(iou >= 0.5)
            ious_ge_07.append(iou >= 0.7)

        # GSTIN checksum validity
        sup_gst = extraction.fields.get("supplier_gstin")
        if sup_gst and sup_gst.field_value:
            v_ok, _ = validate_gstin(sup_gst.field_value)
            gstin_checksum_valid.append(v_ok)
        else:
            gstin_checksum_valid.append(False)

        buy_gst = extraction.fields.get("buyer_gstin")
        if buy_gst and buy_gst.field_value:
            v_ok, _ = validate_gstin(buy_gst.field_value)
            gstin_checksum_valid.append(v_ok)
        else:
            gstin_checksum_valid.append(False)

        # Repairs
        for rep_list in extraction.gstin_repairs.values():
            for rep in rep_list:
                if "Pos " in rep or "Check digit" in rep:
                    gstin_repairs_count += 1

        # Math reconciliation
        math_ok = extraction.math_reconciliation.get("is_valid", False)
        math_reconciled.append(math_ok)

        # QR Decoded
        qr_ok = extraction.qr_data is not None and extraction.qr_data.get("is_decoded", False)
        qr_decoded.append(qr_ok)

        doc_summary = {
            "id": doc_id,
            "is_degraded": is_deg,
            "degradation_type": gt.get("degradation_type", "clean"),
            "matches": doc_field_matches,
            "mean_iou": np.mean(list(extraction.iou_scores.values())) if extraction.iou_scores else 0.0,
            "math_reconciled": math_ok,
            "qr_decoded": qr_ok,
            "latency_ms": round(elapsed_ms, 1),
        }
        records.append(doc_summary)
        if is_deg:
            deg_records.append(doc_summary)
        else:
            clean_records.append(doc_summary)

        print(f"[{idx+1:02d}/{len(doc_ids):02d}] {doc_id:<25} | "
              f"GSTIN Checksum: {'OK' if (sup_gst and sup_gst.is_valid) else 'FAIL'} | "
              f"Math: {'OK' if math_ok else 'FAIL'} | "
              f"QR: {'YES' if qr_ok else 'NO'} | "
              f"Latency: {elapsed_ms:5.1f}ms")

    # Aggregate Statistics
    total_docs = len(records)
    clean_count = len(clean_records)
    deg_count = len(deg_records)

    field_accuracy = {f: round(float(np.mean(vals)) * 100.0, 2) for f, vals in field_matches.items()}
    overall_field_em = round(float(np.mean([np.mean(vals) for vals in field_matches.values()])) * 100.0, 2)

    field_mean_iou = {f: round(float(np.mean(vals)), 4) for f, vals in field_ious.items()}
    overall_iou_ge_05 = round(float(np.mean(ious_ge_05)) * 100.0, 2)
    overall_iou_ge_07 = round(float(np.mean(ious_ge_07)) * 100.0, 2)
    overall_mean_iou = round(float(np.mean([np.mean(vals) for vals in field_ious.values()])), 4)

    gstin_checksum_rate = round(float(np.mean(gstin_checksum_valid)) * 100.0, 2)
    math_reconciliation_rate = round(float(np.mean(math_reconciled)) * 100.0, 2)
    qr_decode_rate = round(float(np.mean(qr_decoded)) * 100.0, 2)

    p50_latency = round(float(np.percentile(latencies, 50)), 1) if latencies else 0.0
    p95_latency = round(float(np.percentile(latencies, 95)), 1) if latencies else 0.0

    # Clean vs Degraded Field EM
    clean_field_matches = [
        np.mean([r["matches"][f] for f in fields_to_track]) for r in clean_records
    ] if clean_records else [0.0]
    deg_field_matches = [
        np.mean([r["matches"][f] for f in fields_to_track]) for r in deg_records
    ] if deg_records else [0.0]

    clean_field_em = round(float(np.mean(clean_field_matches)) * 100.0, 2)
    deg_field_em = round(float(np.mean(deg_field_matches)) * 100.0, 2)

    results = {
        "split": split,
        "engine": engine_name,
        "total_documents": total_docs,
        "clean_documents": clean_count,
        "degraded_documents": deg_count,
        "key_field_em_overall": overall_field_em,
        "key_field_em_clean": clean_field_em,
        "key_field_em_degraded": deg_field_em,
        "gstin_checksum_validity_rate": gstin_checksum_rate,
        "gstin_ocr_repairs_count": gstin_repairs_count,
        "math_tax_reconciliation_rate": math_reconciliation_rate,
        "qr_e_invoice_decode_rate": qr_decode_rate,
        "bounding_box_iou_ge_05_pct": overall_iou_ge_05,
        "bounding_box_iou_ge_07_pct": overall_iou_ge_07,
        "bounding_box_mean_iou": overall_mean_iou,
        "p50_latency_ms": p50_latency,
        "p95_latency_ms": p95_latency,
        "field_accuracy": field_accuracy,
        "field_mean_iou": field_mean_iou,
    }

    # Save results to json
    results_dir = Path("docs/ocr-benchmark/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / f"gst_{split}_{engine_name}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("                  INDIAN GST IDP BENCHMARK RESULTS")
    print("=" * 80)
    print(f" Split:                         {split.upper()} ({total_docs} docs: {clean_count} clean, {deg_count} degraded)")
    print(f" OCR Engine:                    {engine_name}")
    print(f" Key-Field Exact Match (EM):    {overall_field_em}% (Clean: {clean_field_em}%, Degraded: {deg_field_em}%)")
    print(f" GSTIN Checksum Validity Rate:  {gstin_checksum_rate}% ({gstin_repairs_count} OCR confusion repairs applied)")
    print(f" Math Tax Reconciliation Rate:  {math_reconciliation_rate}%")
    print(f" E-Invoice QR Decode Rate:      {qr_decode_rate}%")
    print(f" Bounding Box IoU >= 0.5 Rate:  {overall_iou_ge_05}%")
    print(f" Bounding Box IoU >= 0.7 Rate:  {overall_iou_ge_07}%")
    print(f" Bounding Box Mean IoU:         {overall_mean_iou}")
    print(f" Latency:                       p50 = {p50_latency} ms, p95 = {p95_latency} ms")
    print("-" * 80)
    print(" Per-Field Breakdown:")
    for f in fields_to_track:
        print(f"   - {f:<20}: Accuracy = {field_accuracy[f]:5.1f}% | Mean IoU = {field_mean_iou[f]:.4f}")
    print("=" * 80 + "\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Indian GST Invoice Benchmark")
    parser.add_argument("--split", type=str, default="test", choices=["train", "dev", "test"], help="Dataset split to evaluate")
    parser.add_argument("--engine", type=str, default="tesseract", help="OCR engine name")
    args = parser.parse_args()

    evaluate_gst_dataset(split=args.split, engine_name=args.engine)
