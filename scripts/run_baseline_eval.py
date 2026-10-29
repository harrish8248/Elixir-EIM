#!/usr/bin/env python3
"""
Baseline Pipeline Evaluation.
Evaluates current raw Tesseract pipeline before any preprocessing, field extraction, or IDP rules.
Writes initial benchmark measurements to docs/OCR_ACCURACY.md.
"""

import json
from pathlib import Path
from PIL import Image
import pytesseract
from apps.api.app.content.idp.evaluation import EvaluationHarness

# Configure Tesseract path
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_CMD).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def baseline_processor(img_path: Path, sample_gt: dict) -> dict:
    """Current baseline pipeline: raw image straight to default Tesseract."""
    img = Image.open(img_path)
    
    # Raw Tesseract call
    try:
        raw_text = pytesseract.image_to_string(img)
    except Exception as e:
        raw_text = f"OCR Error: {e}"

    # Basic baseline classification via naive keyword scan
    text_lower = raw_text.lower()
    if "invoice" in text_lower:
        doc_class = "invoice"
    elif "receipt" in text_lower:
        doc_class = "receipt"
    elif "agreement" in text_lower or "contract" in text_lower or "nda" in text_lower:
        doc_class = "contract"
    elif "purchase order" in text_lower or "p.o." in text_lower:
        doc_class = "purchase_order"
    else:
        doc_class = "other"

    # Baseline has NO field extraction or validation rules
    return {
        "extracted_text": raw_text,
        "classification": doc_class,
        "classification_confidence": 50.0,
        "fields": {},
        "line_items": [],
        "validation": {
            "outcome": "NEEDS_REVIEW",
            "is_approved": False,
            "reasons": ["No automated field extraction in baseline engine"],
        },
    }

def main():
    print("Running baseline evaluation on Dev and Test splits...")
    harness = EvaluationHarness()

    dev_baseline = harness.evaluate_pipeline(baseline_processor, split_name="dev", engine_name="baseline_raw_tesseract")
    test_baseline = harness.evaluate_pipeline(baseline_processor, split_name="test", engine_name="baseline_raw_tesseract")

    print(f"Dev CER: {dev_baseline['text_quality']['overall_cer']}% | WER: {dev_baseline['text_quality']['overall_wer']}%")
    print(f"Test CER: {test_baseline['text_quality']['overall_cer']}% | WER: {test_baseline['text_quality']['overall_wer']}%")
    print(f"Test Classification Accuracy: {test_baseline['classification']['accuracy']}%")
    print(f"Test STP Rate: {test_baseline['business_metrics']['stp_rate']}%")

    # Save baseline results JSON
    out_dir = Path("docs/ocr-benchmark/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "baseline_dev.json", "w", encoding="utf-8") as f:
        json.dump(dev_baseline, f, indent=2)
    with open(out_dir / "baseline_test.json", "w", encoding="utf-8") as f:
        json.dump(test_baseline, f, indent=2)

    print("Baseline evaluation completed successfully.")

if __name__ == "__main__":
    main()

