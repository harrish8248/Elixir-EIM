# Elixir EIM — OCR & Intelligent Document Processing (IDP) Accuracy Report

**Date:** 2026-10-28  
**Evaluation Standard:** Measured via `elixir-admin ocr evaluate --split test`  
**Dataset:** 190 labeled documents (80 clean invoices, 80 degraded invoices, 10 receipts, 10 contracts, 10 purchase orders) with ground-truth field JSON.  
**Fixed Seed:** `42` | **Data Split:** Train (50% / 95 docs), Dev (24.2% / 46 docs), Test (25.8% / 49 docs)  
**Strict Policy:** No training on the test set; all reported final numbers are strictly evaluated on the held-out `test` split.

---

## 1. Executive Summary: Baseline vs. Final Target

| Metric | Baseline (Raw Tesseract) | Final Target |
|:---|:---:|:---:|
| **Overall CER (Character Error Rate)** | **57.01%** | < 10.0% |
| **Clean Document CER** | **56.77%** | < 5.0% |
| **Degraded Document CER** | **57.35%** | < 15.0% |
| **Overall WER (Word Error Rate)** | **69.86%** | < 15.0% |
| **Key-Field Exact Match (Clean)** | **0.0%** | > 95.0% |
| **Key-Field Exact Match (Degraded)** | **0.0%** | > 85.0% |
| **Line-Item Extraction Accuracy** | **0.0%** | > 80.0% |
| **Document Classification Accuracy** | **97.96%** | > 99.0% |
| **Straight-Through Processing (STP) Rate**| **0.0%** | > 50.0% |
| **Processing Latency (p50)** | **303.0 ms** | < 600 ms |
| **Processing Latency (p95)** | **393.3 ms** | < 1200 ms |

---

## 2. Phase 1: Measured Baseline Numbers (Raw Tesseract Pipeline)

*Evaluated on Held-Out Test Split (49 Documents: 20 clean invoices, 20 degraded invoices, 3 receipts, 3 contracts, 3 purchase orders)*

```json
{
  "engine": "baseline_raw_tesseract",
  "split": "test",
  "sample_count": 49,
  "text_quality": {
    "overall_cer": 57.01,
    "overall_wer": 69.86,
    "clean_cer": 56.77,
    "clean_wer": 68.94,
    "degraded_cer": 57.35,
    "degraded_wer": 71.20
  },
  "field_extraction": {
    "overall_key_field_exact_match": 0.0,
    "clean_key_field_exact_match": 0.0,
    "degraded_key_field_exact_match": 0.0,
    "line_item_accuracy": 0.0
  },
  "classification": {
    "accuracy": 97.96,
    "confusion_matrix": {
      "contract": {"contract": 3},
      "invoice": {"invoice": 39, "other": 1},
      "purchase_order": {"purchase_order": 3},
      "receipt": {"receipt": 3}
    }
  },
  "business_metrics": {
    "stp_rate": 0.0,
    "stp_auto_approved": 0,
    "stp_eligible_invoices": 40
  },
  "latency": {
    "p50_ms": 303.0,
    "p95_ms": 393.3
  }
}
```

### Baseline Observations
1. **Zero Field Extraction**: The raw pipeline extracted string blobs into PostgreSQL `document_text`, but possessed zero field-level extraction (Vendor, Invoice Number, PO, Line Items, Totals were completely unextracted: 0.0% EM).
2. **Degraded Inability**: Documents rotated 90 degrees or skewed failed completely, producing garbage character streams or misclassification as `"other"`.
3. **Zero STP**: Because no fields or mathematical business rules were validated, straight-through automation was 0.0%.

---

## 3. Ablation Study: Preprocessing & Multi-Pass Optimization (Measured on Dev Split)

*(To be updated iteratively during Phase 2)*

| Iteration / Technique | Dev CER (%) | Dev WER (%) | Δ CER | Δ WER | Latency (p50 ms) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Baseline (Single-Pass Raw Tesseract)** | 58.28% | 71.68% | — | — | 298.5 ms |
| **+ Step 1: 300 DPI Rendering & Native PDF Text Layer** | *pending* | *pending* | *pending* | *pending* | *pending* |
| **+ Step 2: Grayscale & Contrast CLAHE** | *pending* | *pending* | *pending* | *pending* | *pending* |
| **+ Step 3: Bilateral Denoising & Adaptive Thresholding** | *pending* | *pending* | *pending* | *pending* | *pending* |
| **+ Step 4: Deskew & Tesseract OSD Orientation Fix** | *pending* | *pending* | *pending* | *pending* | *pending* |
| **+ Step 5: Multi-Pass PSM & TSV Word Confidence Selection** | *pending* | *pending* | *pending* | *pending* | *pending* |
