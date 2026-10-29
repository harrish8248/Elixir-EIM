"""Unit tests for Indian GSTIN Base-36 checksum, OCR confusion repair, and offline QR decoding."""

import base64
import json
import pytest

from apps.api.app.content.idp.gstin import (
    calculate_iou,
    compute_gstin_check_char,
    decode_einvoice_qr,
    repair_gstin_ocr,
    validate_gstin,
)


def test_gstin_checksum_valid_vector():
    """Verify test vector 27AAPFU0939F1ZV is strictly valid."""
    is_valid, err = validate_gstin("27AAPFU0939F1ZV")
    assert is_valid is True, f"Expected valid GSTIN, got error: {err}"
    assert err is None


def test_gstin_checksum_invalid_vector():
    """Verify test vector 27AAPFU0939F1ZX is strictly invalid."""
    is_valid, err = validate_gstin("27AAPFU0939F1ZX")
    assert is_valid is False
    assert "Checksum mismatch" in (err or "")


def test_gstin_check_char_computation():
    """Verify Base-36 checksum character computation."""
    check_char = compute_gstin_check_char("27AAPFU0939F1Z")
    assert check_char == "V"


def test_gstin_ocr_confusion_repair():
    """Verify position-aware letter/digit OCR confusion repair."""
    # State code '2' misread as 'Z', check char 'V' misread as 'X'
    corrupted = "Z7AAPFU0939F1ZX"
    repaired, conf, repairs = repair_gstin_ocr(corrupted)
    assert repaired == "27AAPFU0939F1ZV", f"Expected repaired GSTIN, got {repaired}"
    assert conf >= 0.8
    assert len(repairs) > 0


def test_gstin_qr_offline_decoding():
    """Verify offline e-invoice JWT QR code decoding."""
    payload = {
        "SellerGstin": "27AAPFU0939F1ZV",
        "BuyerGstin": "29AABCU9603R1ZM",
        "DocNo": "INV-2026-GST-001",
        "DocDate": "2026-10-29",
        "TotInvVal": 118000.0,
        "Irn": "f12a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a",
    }
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    fake_jwt = f"eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.{encoded_payload}.fake_signature_bytes_not_needed_for_offline"

    decoded = decode_einvoice_qr(fake_jwt)
    assert decoded is not None
    assert decoded["seller_gstin"] == "27AAPFU0939F1ZV"
    assert decoded["buyer_gstin"] == "29AABCU9603R1ZM"
    assert decoded["doc_no"] == "INV-2026-GST-001"
    assert decoded["total_value"] == 118000.0


def test_iou_tracking():
    """Verify bounding box IoU calculation."""
    # Identical boxes
    box1 = [100.0, 100.0, 200.0, 200.0]
    box2 = [100.0, 100.0, 200.0, 200.0]
    assert calculate_iou(box1, box2) == 1.0

    # Half overlap
    box3 = [100.0, 100.0, 200.0, 200.0]
    box4 = [150.0, 100.0, 250.0, 200.0]
    iou = calculate_iou(box3, box4)
    assert 0.3 <= iou <= 0.4

    # Disjoint boxes
    box5 = [0.0, 0.0, 50.0, 50.0]
    box6 = [100.0, 100.0, 150.0, 150.0]
    assert calculate_iou(box5, box6) == 0.0
