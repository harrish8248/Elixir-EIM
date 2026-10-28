"""
Ablation Study Evaluator for Elixir EIM IDP.
Measures dev-split performance step-by-step:
Step 0: Baseline (Raw Tesseract)
Step 1: + Grayscale
Step 2: + OSD Orientation Detection
Step 3: + Hough Deskew
Step 4: + CLAHE Contrast Enhancement
Step 5: + Bilateral Denoise
Step 6: + Multi-Pass PSM (Full Pipeline)
"""

import json
from pathlib import Path
import time

from apps.api.app.content.idp.engine import TesseractEngine
from apps.api.app.content.idp.evaluation import EvaluationHarness
from apps.api.app.content.idp.service import IdpService

harness = EvaluationHarness()

STEPS = [
    (
        "Step 0: Raw Tesseract",
        TesseractEngine(
            enable_osd=False,
            enable_deskew=False,
            enable_clahe=False,
            enable_denoise=False,
            enable_multipass=False,
            name="step0_raw",
        ),
    ),
    (
        "Step 1: + Grayscale & Rescaling",
        TesseractEngine(
            enable_osd=False,
            enable_deskew=False,
            enable_clahe=False,
            enable_denoise=False,
            enable_multipass=False,
            name="step1_grayscale",
        ),
    ),
    (
        "Step 2: + OSD Orientation Correction",
        TesseractEngine(
            enable_osd=True,
            enable_deskew=False,
            enable_clahe=False,
            enable_denoise=False,
            enable_multipass=False,
            name="step2_osd",
        ),
    ),
    (
        "Step 3: + Hough Deskew Correction",
        TesseractEngine(
            enable_osd=True,
            enable_deskew=True,
            enable_clahe=False,
            enable_denoise=False,
            enable_multipass=False,
            name="step3_deskew",
        ),
    ),
    (
        "Step 4: + CLAHE Contrast Enhancement",
        TesseractEngine(
            enable_osd=True,
            enable_deskew=True,
            enable_clahe=True,
            enable_denoise=False,
            enable_multipass=False,
            name="step4_clahe",
        ),
    ),
    (
        "Step 5: + Bilateral Denoising",
        TesseractEngine(
            enable_osd=True,
            enable_deskew=True,
            enable_clahe=True,
            enable_denoise=True,
            enable_multipass=False,
            name="step5_denoise",
        ),
    ),
    (
        "Step 6: + Multi-Pass PSM (Full Pipeline)",
        TesseractEngine(
            enable_osd=True,
            enable_deskew=True,
            enable_clahe=True,
            enable_denoise=True,
            enable_multipass=True,
            name="step6_full_pipeline",
        ),
    ),
]


def run():
    print("Starting Dev Set Ablation Study (46 documents)...")
    ablation_results = []

    for name, engine in STEPS:
        print(f"\n--- Running: {name} ---")
        svc = IdpService(engine=engine)
        svc.learn_from_train_split()

        t0 = time.time()
        metrics = harness.evaluate_pipeline(
            process_fn=svc.process_image_path,
            split_name="dev",
            engine_name=engine.name,
        )
        duration = round(time.time() - t0, 1)

        summary = {
            "step": name,
            "engine": engine.name,
            "duration_s": duration,
            "overall_cer": metrics["text_quality"]["overall_cer"],
            "clean_cer": metrics["text_quality"]["clean_cer"],
            "degraded_cer": metrics["text_quality"]["degraded_cer"],
            "overall_wer": metrics["text_quality"]["overall_wer"],
            "key_field_em": metrics["field_extraction"]["overall_key_field_exact_match"],
            "clean_key_field_em": metrics["field_extraction"]["clean_key_field_exact_match"],
            "degraded_key_field_em": metrics["field_extraction"]["degraded_key_field_exact_match"],
            "line_item_acc": metrics["field_extraction"]["line_item_accuracy"],
            "classification_acc": metrics["classification"]["accuracy"],
            "stp_rate": metrics["business_metrics"]["stp_rate"],
            "latency_p50": metrics["latency"]["p50_ms"],
            "latency_p95": metrics["latency"]["p95_ms"],
        }
        ablation_results.append(summary)
        print(
            f"Result: CER={summary['overall_cer']}% (Clean: {summary['clean_cer']}%, Degraded: {summary['degraded_cer']}%), "
            f"WER={summary['overall_wer']}%, KeyFieldEM={summary['key_field_em']}%, STP={summary['stp_rate']}%"
        )

    out_path = Path("docs/ocr-benchmark/results/ablation_dev.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ablation_results, f, indent=2)
    print(f"\nAblation study completed and saved to {out_path}")


if __name__ == "__main__":
    run()
