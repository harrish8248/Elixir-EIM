"""
Unit & Regression Test Suite for Elixir EIM IDP (Vendor Invoice Management).
Tests:
- Normalizers (dates, amounts, currency, invoice/PO numbers)
- Business Validation Rules (Math, Line Items, Required, Date sanity, Duplicates, PO match, Vendor master)
- Document Classification
- Continuous Learning Priors
- Accuracy Regression Gate
"""

import json
from pathlib import Path
import pytest

from apps.api.app.content.idp.classifier import DocumentClassifier
from apps.api.app.content.idp.learning import LearnedFieldPrior, VendorTemplateStore
from apps.api.app.content.idp.models import BoundingBox, DocumentType, ExtractedField, LineItem
from apps.api.app.content.idp.normalizers import (
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_invoice_number,
    normalize_po_number,
)
from apps.api.app.content.idp.validation import ValidationEngine


def test_normalizers():
    # Dates
    assert normalize_date("2026-05-08") == "2026-05-08"
    assert normalize_date("05/08/2026") == "2026-05-08"
    assert normalize_date("May 8, 2026") == "2026-05-08"
    assert normalize_date("8th May 2026") == "2026-05-08"

    # Amounts
    assert normalize_amount("$1,234.56") == 1234.56
    assert normalize_amount("€ 1.234,56") == 1234.56
    assert normalize_amount("(450.00)") == -450.00
    assert normalize_amount("6089") == 6089.0

    # Currencies
    assert normalize_currency("$") == "USD"
    assert normalize_currency("EUR") == "EUR"
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("£") == "GBP"

    # Invoice / PO numbers
    assert normalize_invoice_number("Invoice #: INV-2026-1000") == "INV-2026-1000"
    assert normalize_invoice_number("INV-2026-1000.") == "INV-2026-1000"
    assert normalize_po_number("PO Number: PO-2026-7000") == "PO-2026-7000"


def test_validation_math_reconciliation():
    engine = ValidationEngine()

    # Valid math: 100 + 10 = 110
    fields_valid = {
        "vendor": ExtractedField(field_name="vendor", field_value="CloudScale Networks Inc", confidence=0.98),
        "invoice_number": ExtractedField(field_name="invoice_number", field_value="INV-001", confidence=0.98),
        "invoice_date": ExtractedField(field_name="invoice_date", field_value="2026-05-01", confidence=0.98),
        "subtotal": ExtractedField(field_name="subtotal", field_value=100.0, confidence=0.98),
        "tax": ExtractedField(field_name="tax", field_value=10.0, confidence=0.98),
        "total": ExtractedField(field_name="total", field_value=110.0, confidence=0.98),
    }
    summary = engine.validate(fields_valid, [])
    assert any(r.rule_name == "math_subtotal_tax_total" and r.passed for r in summary.rules)
    assert summary.is_approved is True

    # Invalid math: 100 + 10 != 125
    fields_invalid = dict(fields_valid)
    fields_invalid["total"] = ExtractedField(field_name="total", field_value=125.0, confidence=0.98)
    summary_invalid = engine.validate(fields_invalid, [])
    assert any(r.rule_name == "math_subtotal_tax_total" and not r.passed for r in summary_invalid.rules)
    assert summary_invalid.is_approved is False


def test_validation_required_fields():
    engine = ValidationEngine()
    fields_missing = {
        "invoice_number": ExtractedField(field_name="invoice_number", field_value="INV-001", confidence=0.98),
        "total": ExtractedField(field_name="total", field_value=500.0, confidence=0.98),
    }
    summary = engine.validate(fields_missing, [])
    assert any(r.rule_name == "required_fields_present" and not r.passed for r in summary.rules)
    assert summary.is_approved is False


def test_validation_date_sanity():
    engine = ValidationEngine()
    fields_dates = {
        "vendor": ExtractedField(field_name="vendor", field_value="CloudScale Networks Inc", confidence=0.98),
        "invoice_number": ExtractedField(field_name="invoice_number", field_value="INV-001", confidence=0.98),
        "invoice_date": ExtractedField(field_name="invoice_date", field_value="2026-05-20", confidence=0.98),
        "due_date": ExtractedField(field_name="due_date", field_value="2026-05-10", confidence=0.98),  # due before issue
        "total": ExtractedField(field_name="total", field_value=100.0, confidence=0.98),
    }
    summary = engine.validate(fields_dates, [])
    assert any(r.rule_name == "date_sanity" and not r.passed for r in summary.rules)
    assert summary.is_approved is False


def test_validation_duplicate_detection():
    existing = {("cloudscale networks inc", "inv-2026-1000", 6089.0)}
    engine = ValidationEngine(existing_invoices=existing)

    fields_dup = {
        "vendor": ExtractedField(field_name="vendor", field_value="CloudScale Networks Inc", confidence=0.98),
        "invoice_number": ExtractedField(field_name="invoice_number", field_value="INV-2026-1000", confidence=0.98),
        "invoice_date": ExtractedField(field_name="invoice_date", field_value="2026-05-08", confidence=0.98),
        "total": ExtractedField(field_name="total", field_value=6089.0, confidence=0.98),
    }
    summary = engine.validate(fields_dup, [])
    assert any(r.rule_name == "duplicate_check" and not r.passed for r in summary.rules)
    assert summary.is_approved is False


def test_validation_po_matching():
    engine = ValidationEngine()

    fields_po_ok = {
        "vendor": ExtractedField(field_name="vendor", field_value="CloudScale Networks Inc", confidence=0.98),
        "invoice_number": ExtractedField(field_name="invoice_number", field_value="INV-2026-1000", confidence=0.98),
        "invoice_date": ExtractedField(field_name="invoice_date", field_value="2026-05-08", confidence=0.98),
        "po_number": ExtractedField(field_name="po_number", field_value="PO-2026-7000", confidence=0.98),
        "subtotal": ExtractedField(field_name="subtotal", field_value=6089.0, confidence=0.98),
        "tax": ExtractedField(field_name="tax", field_value=0.0, confidence=0.98),
        "total": ExtractedField(field_name="total", field_value=6089.0, confidence=0.98),
    }
    summary_ok = engine.validate(fields_po_ok, [])
    assert any(r.rule_name == "po_matching" and r.passed for r in summary_ok.rules)

    # PO price mismatch
    fields_po_bad = dict(fields_po_ok)
    fields_po_bad["total"] = ExtractedField(field_name="total", field_value=7500.0, confidence=0.98)
    fields_po_bad["subtotal"] = ExtractedField(field_name="subtotal", field_value=7500.0, confidence=0.98)
    summary_bad = engine.validate(fields_po_bad, [])
    assert any(r.rule_name == "po_matching" and not r.passed for r in summary_bad.rules)


def test_document_classification():
    classifier = DocumentClassifier()

    inv_text = "TAX INVOICE Invoice #: INV-2026-1000 Total Amount Due: $6,089.00 Bill To: AcroCorp"
    doc_type, conf = classifier.classify(inv_text)
    assert doc_type == DocumentType.INVOICE
    assert conf > 0.60

    po_text = "PURCHASE ORDER P.O. #: PO-2026-7000 Issued By AcroCorp Procurement Order Date: 2026-10-12"
    po_type, po_conf = classifier.classify(po_text)
    assert po_type == DocumentType.PURCHASE_ORDER
    assert po_conf > 0.60

    contract_text = "MUTUAL CONFIDENTIALITY AND NONDISCLOSURE AGREEMENT IN WITNESS WHEREOF the parties have executed"
    cnt_type, cnt_conf = classifier.classify(contract_text)
    assert cnt_type == DocumentType.CONTRACT
    assert cnt_conf > 0.60


def test_continuous_learning_priors(tmp_path):
    store = VendorTemplateStore(storage_path=tmp_path / "templates.json")
    bbox = BoundingBox(x=100, y=200, width=150, height=30)
    store.record_correction("Acme Corp", "invoice_number", bbox, page_width=1000, page_height=1000)

    prior = store.templates["Acme Corp"]["invoice_number"]
    assert prior.rel_x == 0.1
    assert prior.rel_y == 0.2
    assert prior.rel_w == 0.15
    assert prior.rel_h == 0.03
    assert prior.sample_count == 1


def test_idp_accuracy_regression_gate():
    """
    Regression gate: verifies that held-out test split metrics strictly exceed
    the committed baseline and meet production targets.
    """
    results_path = Path("docs/ocr-benchmark/results/evaluation_test.json")
    assert results_path.exists(), "Evaluation results for test split must exist"

    with open(results_path, encoding="utf-8") as f:
        metrics = json.load(f)

    # 1. Clean Key-Field Exact Match must exceed 80% (baseline was 0.0%)
    clean_em = metrics["field_extraction"]["clean_key_field_exact_match"]
    assert clean_em >= 80.0, f"Clean Key-Field EM ({clean_em}%) below threshold (80.0%)"

    # 2. Straight-Through Processing (STP) rate must exceed 50% (baseline was 0.0%)
    stp_rate = metrics["business_metrics"]["stp_rate"]
    assert stp_rate >= 50.0, f"STP Rate ({stp_rate}%) below threshold (50.0%)"

    # 3. Document classification accuracy must exceed 98%
    class_acc = metrics["classification"]["accuracy"]
    assert class_acc >= 98.0, f"Classification accuracy ({class_acc}%) below threshold (98.0%)"

    # 4. Latency p95 must be under 4000ms
    p95_ms = metrics["latency"]["p95_ms"]
    assert p95_ms <= 4000.0, f"Processing latency p95 ({p95_ms}ms) exceeded 4000ms"
