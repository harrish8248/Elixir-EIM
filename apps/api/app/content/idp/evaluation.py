"""
Evaluation Harness for Elixir EIM OCR & Intelligent Document Processing (IDP).
Computes real, measured metrics across Train, Dev, and Test splits:
- Character Error Rate (CER)
- Word Error Rate (WER)
- Per-field Exact-Match (EM) Accuracy
- Per-field Precision, Recall, and F1
- Line-item extraction accuracy
- Document classification accuracy and Confusion Matrix
- Confidence calibration (accuracy per confidence bucket)
- Straight-Through-Processing (STP) Rate
- Page Processing Latency (p50, p95)
"""

import json
import math
import re
import time
from collections import defaultdict
import os
from pathlib import Path
from typing import Any

BENCHMARK_DIR = Path(os.environ.get("ELIXIR_DATA_DIR", "docs/ocr-benchmark"))
DATA_DIR = BENCHMARK_DIR / "data"
SPLITS_PATH = BENCHMARK_DIR / "splits.json"


def normalize_eval_text(text: Any) -> str:
    """Normalize text for CER/WER evaluation: collapse whitespace runs, lowercase, strip."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def levenshtein_distance(seq1: list | str, seq2: list | str) -> int:
    """Compute Levenshtein edit distance between two sequences (chars or tokens)."""
    n, m = len(seq1), len(seq2)
    if n < m:
        return levenshtein_distance(seq2, seq1)
    if m == 0:
        return n

    prev_row = list(range(m + 1))
    for i, item1 in enumerate(seq1):
        curr_row = [i + 1]
        for j, item2 in enumerate(seq2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (item1 != item2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def compute_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate: edit_dist(chars) / len(ref_chars)."""
    ref = normalize_eval_text(reference)
    hyp = normalize_eval_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    dist = levenshtein_distance(list(ref), list(hyp))
    return min(dist / max(len(ref), 1), 1.0)


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate: edit_dist(words) / len(ref_words)."""
    ref_norm = normalize_eval_text(reference)
    hyp_norm = normalize_eval_text(hypothesis)
    ref_words = ref_norm.split()
    hyp_words = hyp_norm.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(ref_words, hyp_words)
    return min(dist / max(len(ref_words), 1), 1.0)


def wilson_confidence_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Compute Wilson score 95% confidence interval for proportion k / n.
    Returns (low_pct, high_pct) as percentages in [0, 100].
    """
    if n <= 0:
        return (0.0, 0.0)
    z = 1.95996  # 95% confidence z-score
    if k <= 0:
        high = (z * z / (2 * n)) / (1 + z * z / n)
        return (0.0, round(high * 100, 2))
    if k >= n:
        low = (n + z * z / 2 - z * math.sqrt(z * z / 4)) / (n + z * z)
        return (round(low * 100, 2), 100.0)

    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    spread = (z / denominator) * math.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))
    low = max(0.0, center - spread)
    high = min(1.0, center + spread)
    return (round(low * 100, 2), round(high * 100, 2))


def normalize_text_match(text: Any) -> str:
    """Normalize text for semantic exact-match comparison."""
    if text is None:
        return ""
    return str(text).strip().lower().replace(",", "").replace("-", "").replace(" ", "")


class EvaluationHarness:
    """Evaluates IDP pipeline against labeled ground truth splits."""

    def __init__(self, splits_file: Path = SPLITS_PATH, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        with open(splits_file, encoding="utf-8") as f:
            self.splits = json.load(f)

    def load_split_samples(self, split_name: str) -> list[dict[str, Any]]:
        """Load ground truth metadata for a specific split."""
        if split_name not in self.splits:
            raise ValueError(f"Unknown split '{split_name}'. Available: train, dev, test")
        doc_ids = self.splits[split_name]
        samples = []
        for doc_id in doc_ids:
            gt_file = self.data_dir / f"{doc_id}.json"
            if gt_file.exists():
                with open(gt_file, encoding="utf-8") as f:
                    samples.append(json.load(f))
        return samples

    def evaluate_pipeline(
        self,
        process_fn,
        split_name: str = "test",
        engine_name: str = "tesseract_idp",
    ) -> dict[str, Any]:
        """
        Run end-to-end evaluation on a split using the given processor function.
        process_fn receives (image_path: Path, doc_gt: dict) -> dict of:
          - extracted_text: str
          - classification: str
          - classification_confidence: float
          - fields: dict[str, dict] (value, confidence, etc.)
          - validation: dict (is_approved, reasons, rules)
          - latency_ms: float
        """
        samples = self.load_split_samples(split_name)
        if not samples:
            raise RuntimeError(f"No samples found for split '{split_name}'")

        # Metric accumulators
        cer_scores = []
        wer_scores = []
        cer_clean = []
        wer_clean = []
        cer_degraded = []
        wer_degraded = []
        latencies = []

        # Classification metrics
        class_true = []
        class_pred = []
        classes = sorted(list({s.get("document_type", "other") for s in samples}))

        # Per-field tracking
        field_names = [
            "vendor",
            "invoice_number",
            "invoice_date",
            "due_date",
            "po_number",
            "currency",
            "subtotal",
            "tax",
            "total",
        ]
        field_stats = {
            f: {
                "exact_match": 0,
                "clean_exact_match": 0,
                "degraded_exact_match": 0,
                "total_present": 0,
                "clean_present": 0,
                "degraded_present": 0,
                "tp": 0,
                "fp": 0,
                "fn": 0,
            }
            for f in field_names
        }

        # Calibration buckets: [0, 50), [50, 70), [70, 90), [90, 100]
        calibration_buckets = {
            "0-50%": {"correct": 0, "total": 0},
            "50-70%": {"correct": 0, "total": 0},
            "70-90%": {"correct": 0, "total": 0},
            "90-100%": {"correct": 0, "total": 0},
        }

        # Straight-Through-Processing (STP) & Auto-Approval Safety
        stp_eligible = 0
        stp_auto_approved = 0
        stp_auto_approved_correct = 0
        stp_auto_approved_false = 0
        line_item_matches = 0
        line_item_total = 0

        for sample in samples:
            img_path = Path(sample["image_path"])
            is_degraded = sample.get("is_degraded", False)
            doc_type = sample.get("document_type", "other")

            t0 = time.perf_counter()
            pred = process_fn(img_path, sample)
            lat_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(lat_ms)

            # 1. Text Accuracy (CER / WER)
            ref_text = sample.get("full_text")
            if not ref_text:
                ref_text = (
                    f"{sample.get('vendor') or ''} "
                    f"{sample.get('invoice_number') or ''} "
                    f"{sample.get('invoice_date') or ''} "
                    f"{sample.get('due_date') or ''} "
                    f"{sample.get('total') or ''} "
                    f"{' '.join(item['description'] for item in sample.get('line_items', []))}"
                )
            hyp_text = pred.get("extracted_text", "")

            cer = compute_cer(ref_text, hyp_text)
            wer = compute_wer(ref_text, hyp_text)
            cer_scores.append(cer)
            wer_scores.append(wer)

            if is_degraded:
                cer_degraded.append(cer)
                wer_degraded.append(wer)
            else:
                cer_clean.append(cer)
                wer_clean.append(wer)

            # 2. Classification
            pred_class = pred.get("classification", "other")
            class_true.append(doc_type)
            class_pred.append(pred_class)

            # 3. Field Extractions (for invoices, receipts, POs)
            pred_fields = pred.get("fields", {})
            sample_all_key_fields_correct = True
            if doc_type in ("invoice", "receipt", "purchase_order"):
                for field_name in field_names:
                    gt_val = sample.get(field_name)
                    pred_entry = pred_fields.get(field_name, {})
                    pred_val = (
                        pred_entry.get("normalized_value")
                        if isinstance(pred_entry, dict)
                        else pred_entry
                    )
                    conf = (
                        pred_entry.get("confidence", 0.0)
                        if isinstance(pred_entry, dict)
                        else 80.0
                    )

                    if gt_val is not None:
                        field_stats[field_name]["total_present"] += 1
                        if is_degraded:
                            field_stats[field_name]["degraded_present"] += 1
                        else:
                            field_stats[field_name]["clean_present"] += 1

                        # Match test
                        matched = False
                        if isinstance(gt_val, (int, float)):
                            try:
                                pred_float = float(pred_val)
                                matched = abs(pred_float - float(gt_val)) <= 0.05
                            except (ValueError, TypeError):
                                matched = False
                        else:
                            matched = (
                                normalize_text_match(gt_val)
                                == normalize_text_match(pred_val)
                            ) and bool(pred_val)

                        # Calibration
                        bucket_key = (
                            "0-50%"
                            if conf < 50
                            else "50-70%"
                            if conf < 70
                            else "70-90%"
                            if conf < 90
                            else "90-100%"
                        )
                        calibration_buckets[bucket_key]["total"] += 1
                        if matched:
                            calibration_buckets[bucket_key]["correct"] += 1

                        if matched:
                            field_stats[field_name]["exact_match"] += 1
                            field_stats[field_name]["tp"] += 1
                            if is_degraded:
                                field_stats[field_name]["degraded_exact_match"] += 1
                            else:
                                field_stats[field_name]["clean_exact_match"] += 1
                        else:
                            # If a key field (vendor, inv_num, date, total) failed match, mark document as imperfect
                            if field_name in ("vendor", "invoice_number", "invoice_date", "total"):
                                sample_all_key_fields_correct = False
                            if pred_val:
                                field_stats[field_name]["fp"] += 1
                            else:
                                field_stats[field_name]["fn"] += 1
                    else:
                        if pred_val:
                            field_stats[field_name]["fp"] += 1

                # Line item evaluation
                gt_items = sample.get("line_items", [])
                pred_items = pred.get("line_items", [])
                line_item_total += max(len(gt_items), 1)
                # Count matching items
                matched_items = 0
                for gi in gt_items:
                    for pi in pred_items:
                        if abs(pi.get("amount", 0.0) - gi.get("amount", 0.0)) <= 0.05:
                            matched_items += 1
                            break
                line_item_matches += min(matched_items, len(gt_items))

                # STP Evaluation
                if doc_type == "invoice":
                    stp_eligible += 1
                    val_res = pred.get("validation", {})
                    # Straight-through if approved with zero review reasons
                    is_auto_approved = val_res.get("outcome") == "AUTO_APPROVED" or val_res.get("is_approved", False)
                    if is_auto_approved:
                        stp_auto_approved += 1
                        if sample_all_key_fields_correct:
                            stp_auto_approved_correct += 1
                        else:
                            stp_auto_approved_false += 1

        # Calculate final metrics
        mean_cer = round(float(sum(cer_scores) / max(len(cer_scores), 1) * 100), 2)
        mean_wer = round(float(sum(wer_scores) / max(len(wer_scores), 1) * 100), 2)
        clean_cer = round(float(sum(cer_clean) / max(len(cer_clean), 1) * 100), 2) if cer_clean else 0.0
        clean_wer = round(float(sum(wer_clean) / max(len(wer_clean), 1) * 100), 2) if wer_clean else 0.0
        deg_cer = round(float(sum(cer_degraded) / max(len(cer_degraded), 1) * 100), 2) if cer_degraded else 0.0
        deg_wer = round(float(sum(wer_degraded) / max(len(wer_degraded), 1) * 100), 2) if wer_degraded else 0.0

        # Latency percentiles
        sorted_lat = sorted(latencies)
        p50_lat = round(sorted_lat[int(len(sorted_lat) * 0.50)], 1) if sorted_lat else 0.0
        p95_lat = round(sorted_lat[int(len(sorted_lat) * 0.95)], 1) if sorted_lat else 0.0

        # Classification accuracy & confusion matrix
        correct_class = sum(1 for t, p in zip(class_true, class_pred) if t == p)
        class_acc = round((correct_class / max(len(class_true), 1)) * 100, 2)
        
        confusion_matrix = defaultdict(lambda: defaultdict(int))
        for t, p in zip(class_true, class_pred):
            confusion_matrix[t][p] += 1

        # Per-field calculations
        per_field_results = {}
        total_key_exact = 0
        total_key_total = 0
        total_clean_exact = 0
        total_clean_total = 0
        total_deg_exact = 0
        total_deg_total = 0

        for fname, stat in field_stats.items():
            tot = stat["total_present"]
            em = stat["exact_match"]
            tp = stat["tp"]
            fp = stat["fp"]
            fn = stat["fn"]

            em_pct = round((em / max(tot, 1)) * 100, 2) if tot > 0 else 0.0
            prec = round((tp / max(tp + fp, 1)) * 100, 2)
            rec = round((tp / max(tp + fn, 1)) * 100, 2)
            f1 = round((2 * prec * rec) / max(prec + rec, 0.001), 2)

            clean_tot = stat["clean_present"]
            clean_em = stat["clean_exact_match"]
            clean_em_pct = round((clean_em / max(clean_tot, 1)) * 100, 2) if clean_tot > 0 else 0.0

            deg_tot = stat["degraded_present"]
            deg_em = stat["degraded_exact_match"]
            deg_em_pct = round((deg_em / max(deg_tot, 1)) * 100, 2) if deg_tot > 0 else 0.0

            per_field_results[fname] = {
                "exact_match_pct": em_pct,
                "clean_exact_match_pct": clean_em_pct,
                "degraded_exact_match_pct": deg_em_pct,
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "total_samples": tot,
            }

            total_key_exact += em
            total_key_total += tot
            total_clean_exact += clean_em
            total_clean_total += clean_tot
            total_deg_exact += deg_em
            total_deg_total += deg_tot

        key_field_em = round((total_key_exact / max(total_key_total, 1)) * 100, 2)
        key_field_clean_em = round((total_clean_exact / max(total_clean_total, 1)) * 100, 2)
        key_field_deg_em = round((total_deg_exact / max(total_deg_total, 1)) * 100, 2)

        line_item_acc = round((line_item_matches / max(line_item_total, 1)) * 100, 2)
        stp_rate = round((stp_auto_approved / max(stp_eligible, 1)) * 100, 2)
        stp_ci = wilson_confidence_interval(stp_auto_approved, stp_eligible)

        auto_appr_precision = (
            round((stp_auto_approved_correct / max(stp_auto_approved, 1)) * 100, 2)
            if stp_auto_approved > 0
            else 100.0
        )
        auto_appr_precision_ci = wilson_confidence_interval(stp_auto_approved_correct, stp_auto_approved)

        false_approval_rate = (
            round((stp_auto_approved_false / max(stp_auto_approved, 1)) * 100, 2)
            if stp_auto_approved > 0
            else 0.0
        )
        false_approval_ci = wilson_confidence_interval(stp_auto_approved_false, stp_auto_approved)

        class_acc_ci = wilson_confidence_interval(correct_class, len(class_true))
        key_field_em_ci = wilson_confidence_interval(total_key_exact, total_key_total)

        # Calibration summary
        calibration_results = {}
        for bname, bdata in calibration_buckets.items():
            acc = round((bdata["correct"] / max(bdata["total"], 1)) * 100, 2) if bdata["total"] > 0 else 0.0
            calibration_results[bname] = {
                "accuracy_pct": acc,
                "count": bdata["total"],
                "correct": bdata["correct"],
            }

        report = {
            "engine": engine_name,
            "split": split_name,
            "sample_count": len(samples),
            "text_quality": {
                "overall_cer": mean_cer,
                "overall_wer": mean_wer,
                "clean_cer": clean_cer,
                "clean_wer": clean_wer,
                "degraded_cer": deg_cer,
                "degraded_wer": deg_wer,
            },
            "field_extraction": {
                "overall_key_field_exact_match": key_field_em,
                "overall_key_field_exact_match_95ci": key_field_em_ci,
                "clean_key_field_exact_match": key_field_clean_em,
                "degraded_key_field_exact_match": key_field_deg_em,
                "line_item_accuracy": line_item_acc,
                "fields": per_field_results,
            },
            "classification": {
                "accuracy": class_acc,
                "accuracy_95ci": class_acc_ci,
                "confusion_matrix": {k: dict(v) for k, v in confusion_matrix.items()},
            },
            "calibration": calibration_results,
            "business_metrics": {
                "stp_rate": stp_rate,
                "stp_rate_95ci": stp_ci,
                "stp_auto_approved": stp_auto_approved,
                "stp_eligible_invoices": stp_eligible,
                "auto_approved_precision": auto_appr_precision,
                "auto_approved_precision_95ci": auto_appr_precision_ci,
                "false_approval_rate": false_approval_rate,
                "false_approval_rate_95ci": false_approval_ci,
            },
            "latency": {
                "p50_ms": p50_lat,
                "p95_ms": p95_lat,
            },
        }

        return report
