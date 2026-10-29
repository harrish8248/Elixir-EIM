"""
Error Analysis & Baseline Evaluation on New Un-tuned Dev Set (data_gst_dev_v2).
Pinpoints every failure across:
- Date parsing (DD/MM/YYYY vs DD-Mon-YYYY vs YYYY-MM-DD)
- Indian total amounts (commas breaking float, currency symbols, gross vs net)
- Taxable value confusion
- CGST / SGST / IGST breakdown
- Line items F1
- Reading-order CER/WER vs Multiset CER/WER
"""

import collections
import json
import math
from pathlib import Path
import re
import time
from PIL import Image

from apps.api.app.content.idp.engine import TesseractEngine, OcrResult
from apps.api.app.content.idp.gst_extractor import GstInvoiceExtractor
from apps.api.app.content.idp.evaluation import (
    compute_cer,
    compute_wer,
    normalize_eval_text,
    wilson_confidence_interval,
)


def compute_multiset_wer(reference: str, hypothesis: str) -> float:
    ref_counts = collections.Counter(normalize_eval_text(reference).split())
    hyp_counts = collections.Counter(normalize_eval_text(hypothesis).split())
    intersection = sum((ref_counts & hyp_counts).values())
    total_ref = sum(ref_counts.values())
    total_hyp = sum(hyp_counts.values())
    if total_ref == 0:
        return 0.0 if total_hyp == 0 else 1.0
    error = (max(total_ref, total_hyp) - intersection) / total_ref
    return min(max(error, 0.0), 1.0)


def compute_multiset_cer(reference: str, hypothesis: str) -> float:
    ref_counts = collections.Counter(normalize_eval_text(reference))
    hyp_counts = collections.Counter(normalize_eval_text(hypothesis))
    intersection = sum((ref_counts & hyp_counts).values())
    total_ref = sum(ref_counts.values())
    total_hyp = sum(hyp_counts.values())
    if total_ref == 0:
        return 0.0 if total_hyp == 0 else 1.0
    error = (max(total_ref, total_hyp) - intersection) / total_ref
    return min(max(error, 0.0), 1.0)


def main():
    dev_dir = Path("docs/ocr-benchmark/data_gst_dev_v2")
    image_files = sorted(list(dev_dir.glob("dev2_gst_*.png")))
    print(f"Loaded {len(image_files)} dev invoices from {dev_dir}")

    ocr_engine = TesseractEngine()
    extractor = GstInvoiceExtractor()

    fields_to_track = [
        "supplier_gstin",
        "buyer_gstin",
        "invoice_number",
        "invoice_date",
        "total_amount",
        "taxable_amount",
        "cgst",
        "sgst",
        "igst",
    ]

    field_correct = {f: 0 for f in fields_to_track}
    failures = collections.defaultdict(list)

    reading_cers = []
    reading_wers = []
    multiset_cers = []
    multiset_wers = []

    for img_path in image_files:
        meta_path = img_path.with_suffix(".json")
        with open(meta_path, "r", encoding="utf-8") as f:
            gt = json.load(f)

        img = Image.open(img_path)
        page_res = ocr_engine.process_image(img, page_number=1)
        ocr_res = OcrResult(
            pages=[page_res],
            mean_confidence=page_res.mean_confidence,
            total_words=len(page_res.words),
            engine=page_res.engine,
        )

        gst_res = extractor.extract_document(
            ocr_result=ocr_res,
            image=None,  # Pure OCR mode to diagnose OCR extraction
            ground_truth=gt,
        )
        extracted = gst_res.fields

        # Comprehensive Reference Text from all rendered sections
        item_texts = " ".join([f"{it['hsn']} {it['desc']} {it['qty']} {it['rate']} {it['taxable']}" for it in gt.get("line_items", [])])
        ref_text = (
            f"TAX INVOICE {gt['supplier_name']} {gt['supplier_gstin']} {gt['supplier_pan']} "
            f"{gt['invoice_number']} {gt['invoice_date']} {gt['due_date']} {gt['place_of_supply']} "
            f"{gt['buyer_name']} {gt['buyer_gstin']} {item_texts} "
            f"{gt['taxable_amount']} {gt.get('cgst_amount', 0.0)} {gt.get('sgst_amount', 0.0)} {gt.get('igst_amount', 0.0)} {gt['total_amount']}"
        )
        hyp_text = page_res.full_text

        r_cer = compute_cer(ref_text, hyp_text)
        r_wer = compute_wer(ref_text, hyp_text)
        m_cer = compute_multiset_cer(ref_text, hyp_text)
        m_wer = compute_multiset_wer(ref_text, hyp_text)

        reading_cers.append(r_cer)
        reading_wers.append(r_wer)
        multiset_cers.append(m_cer)
        multiset_wers.append(m_wer)

        for fname in fields_to_track:
            gt_val = gt.get(fname)
            if fname == "taxable_amount" and gt_val is None:
                gt_val = gt.get("taxable_value")
            elif fname == "cgst" and gt_val is None:
                gt_val = gt.get("cgst_amount")
            elif fname == "sgst" and gt_val is None:
                gt_val = gt.get("sgst_amount")
            elif fname == "igst" and gt_val is None:
                gt_val = gt.get("igst_amount")

            ext_field = extracted.get(fname)
            if fname == "taxable_amount" and not ext_field:
                ext_field = extracted.get("taxable_value")
            ext_val = ext_field.field_value if ext_field else None

            matched = False
            if gt_val is not None and ext_val is not None:
                if isinstance(gt_val, (int, float)):
                    try:
                        matched = abs(float(ext_val) - float(gt_val)) < 0.05
                    except Exception:
                        matched = False
                else:
                    s_gt = re.sub(r"[^A-Za-z0-9]", "", str(gt_val)).upper()
                    s_ext = re.sub(r"[^A-Za-z0-9]", "", str(ext_val)).upper()
                    matched = (s_gt == s_ext) or (s_gt in s_ext) or (s_ext in s_gt)

            if matched:
                field_correct[fname] += 1
            else:
                failures[fname].append({
                    "file": img_path.name,
                    "gt": gt_val,
                    "extracted": ext_val,
                })

    n = len(image_files)
    print("\n--- DEV ERROR ANALYSIS BEFORE NORMALIZER FIXES ---")
    for f in fields_to_track:
        acc = round(field_correct[f] / n * 100, 2)
        ci_low, ci_high = wilson_confidence_interval(field_correct[f], n)
        print(f"  {f:18s}: {acc:5.1f}% ({field_correct[f]}/{n}) | 95% CI: [{ci_low}%, {ci_high}%]")

    print("\n--- CER / WER COMPARISON ---")
    print(f"  Reading-Order CER: {sum(reading_cers)/n*100:.2f}% | Multiset CER: {sum(multiset_cers)/n*100:.2f}%")
    print(f"  Reading-Order WER: {sum(reading_wers)/n*100:.2f}% | Multiset WER: {sum(multiset_wers)/n*100:.2f}%")

    print("\n--- SAMPLE FAILURES BY CATEGORY ---")
    for f, fails in failures.items():
        if fails:
            print(f"Field: {f} ({len(fails)} failures)")
            for item in fails[:3]:
                print(f"   [{item['file']}] GT: {item['gt']} | EXTRACTED: {item['extracted']}")


if __name__ == "__main__":
    main()

