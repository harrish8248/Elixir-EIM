"""Indian GST Invoice Processing, GSTIN Base-36 Checksum Validation, OCR Confusion Repair, and Offline QR Decoding."""

import base64
import json
import re
from typing import Any

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CHAR_MAP = {c: i for i, c in enumerate(CHARS)}

# Official State Codes under Indian GST
STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

# OCR Confusion dictionaries
DIGIT_FROM_CHAR = {
    "O": "0", "o": "0", "D": "0", "Q": "0",
    "I": "1", "i": "1", "l": "1", "|": "1", "!": "1",
    "Z": "2", "z": "2",
    "E": "3",
    "A": "4",
    "S": "5", "s": "5",
    "G": "6", "b": "6",
    "T": "7",
    "B": "8",
    "g": "9", "q": "9",
}

CHAR_FROM_DIGIT = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "3": "E",
    "4": "A",
    "5": "S",
    "6": "G",
    "7": "T",
    "8": "B",
    "9": "P",
}


def compute_gstin_check_char(gstin14: str) -> str:
    """
    Compute official GST Council Base-36 checksum character for the first 14 characters of a GSTIN.
    """
    total = 0
    clean14 = gstin14.upper().strip()[:14]
    if len(clean14) < 14:
        return ""

    for i, c in enumerate(clean14):
        v = CHAR_MAP.get(c, 0)
        factor = 1 if (i % 2 == 0) else 2
        prod = v * factor
        total += (prod // 36) + (prod % 36)

    rem = total % 36
    check_code = (36 - rem) % 36
    return CHARS[check_code]


def validate_gstin(gstin: str | None) -> tuple[bool, str | None]:
    """
    Validate Indian GSTIN against structure, state code, and Modulus-36 checksum.
    Returns (is_valid, error_message).
    Example valid test vector: 27AAPFU0939F1ZV
    Example invalid vector: 27AAPFU0939F1ZX
    """
    if not gstin:
        return False, "GSTIN is missing or empty"

    clean = re.sub(r"[^A-Za-z0-9]", "", gstin).upper()
    if len(clean) != 15:
        return False, f"Invalid length ({len(clean)} chars instead of 15)"

    state_code = clean[:2]
    if state_code not in STATE_CODES:
        return False, f"Invalid GST state code '{state_code}'"

    pan_chars = clean[2:7]
    if not pan_chars.isalpha():
        return False, f"Positions 3-7 must be alphabetic PAN prefix (got '{pan_chars}')"

    pan_digits = clean[7:11]
    if not pan_digits.isdigit():
        return False, f"Positions 8-11 must be numeric PAN sequence (got '{pan_digits}')"

    pan_check = clean[11]
    if not pan_check.isalpha():
        return False, f"Position 12 must be alphabetic PAN check digit (got '{pan_check}')"

    expected_check = compute_gstin_check_char(clean[:14])
    actual_check = clean[14]
    if expected_check != actual_check:
        return False, f"Checksum mismatch: expected '{expected_check}', got '{actual_check}'"

    return True, None


def repair_gstin_ocr(raw_text: str) -> tuple[str | None, float, list[str]]:
    """
    Position-aware OCR letter/digit confusion repair for Indian GSTINs.
    Repairs common substitutions:
      - Positions 1-2 (digits): O->0, I->1, Z->2, S->5, B->8
      - Positions 3-7 (letters): 0->O, 1->I, 5->S, 8->B, 2->Z
      - Positions 8-11 (digits): O->0, I->1, S->5, B->8
      - Position 12 (letter): 0->O, 1->I, 5->S, 8->B
      - Position 13 (entity): alphanumeric
      - Position 14 (default): 'Z'
      - Position 15 (check char): recomputed if damaged
    A candidate is accepted ONLY if its checksum evaluates to valid.
    Returns (repaired_gstin, confidence, applied_repairs).
    """
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_text).upper()
    if len(cleaned) < 14:
        return None, 0.0, ["Length too short for GSTIN"]

    # If already 15 chars and valid
    if len(cleaned) == 15:
        is_val, _ = validate_gstin(cleaned)
        if is_val:
            return cleaned, 1.0, ["Exact valid match (no repair required)"]

    # Truncate to 14 or 15
    chars = list(cleaned[:15])
    repairs_applied = []

    # Position 1-2: Digits (State code)
    for p in [0, 1]:
        if chars[p] in DIGIT_FROM_CHAR:
            orig = chars[p]
            chars[p] = DIGIT_FROM_CHAR[orig]
            repairs_applied.append(f"Pos {p+1}: '{orig}' -> '{chars[p]}'")

    # Position 3-7: Letters (PAN Prefix)
    for p in range(2, 7):
        if chars[p] in CHAR_FROM_DIGIT:
            orig = chars[p]
            chars[p] = CHAR_FROM_DIGIT[orig]
            repairs_applied.append(f"Pos {p+1}: '{orig}' -> '{chars[p]}'")

    # Position 8-11: Digits (PAN Digits)
    for p in range(7, 11):
        if chars[p] in DIGIT_FROM_CHAR:
            orig = chars[p]
            chars[p] = DIGIT_FROM_CHAR[orig]
            repairs_applied.append(f"Pos {p+1}: '{orig}' -> '{chars[p]}'")

    # Position 12: Letter (PAN Check)
    if chars[11] in CHAR_FROM_DIGIT:
        orig = chars[11]
        chars[11] = CHAR_FROM_DIGIT[orig]
        repairs_applied.append(f"Pos 12: '{orig}' -> '{chars[11]}'")

    # Position 14: Default is 'Z'
    if len(chars) >= 14 and chars[13] != "Z":
        if chars[13] in ("2", "7", "s", "S"):
            orig = chars[13]
            chars[13] = "Z"
            repairs_applied.append(f"Pos 14: '{orig}' -> 'Z'")

    # Position 15: Recompute check char
    first14 = "".join(chars[:14])
    recomputed_check = compute_gstin_check_char(first14)
    if len(chars) < 15:
        chars.append(recomputed_check)
        repairs_applied.append(f"Pos 15: Recomputed check digit '{recomputed_check}'")
    elif chars[14] != recomputed_check:
        orig = chars[14]
        chars[14] = recomputed_check
        repairs_applied.append(f"Pos 15: Check digit repair '{orig}' -> '{recomputed_check}'")

    candidate = "".join(chars[:15])
    is_valid, err = validate_gstin(candidate)
    if is_valid:
        # Confidence decays slightly based on number of repairs
        conf = max(1.0 - (len(repairs_applied) * 0.04), 0.75)
        return candidate, round(conf, 4), repairs_applied

    return None, 0.0, [f"Repair failed checksum validation: {err}"]


def decode_einvoice_qr(qr_data_string: str) -> dict[str, Any] | None:
    """
    Offline decoder for Indian e-Invoice Signed QR Codes (JWT format).
    Decodes the JWT payload without requiring an external internet connection.
    Returns parsed fields (SellerGstin, BuyerGstin, DocNo, DocDate, TotInvVal, Irn).
    """
    if not qr_data_string:
        return None

    # Check for JWT structure: header.payload.signature
    parts = qr_data_string.strip().split(".")
    if len(parts) >= 2:
        try:
            payload_b64 = parts[1]
            # Add padding if necessary
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            decoded_bytes = base64.urlsafe_b64decode(payload_b64)
            payload_json = json.loads(decoded_bytes.decode("utf-8", errors="ignore"))
            # Standard GST e-invoice payload keys
            return {
                "seller_gstin": payload_json.get("SellerGstin") or payload_json.get("seller_gstin"),
                "buyer_gstin": payload_json.get("BuyerGstin") or payload_json.get("buyer_gstin"),
                "doc_no": payload_json.get("DocNo") or payload_json.get("doc_no"),
                "doc_date": payload_json.get("DocDate") or payload_json.get("doc_date"),
                "total_value": payload_json.get("TotInvVal") or payload_json.get("total_amount"),
                "item_count": payload_json.get("ItemCnt"),
                "main_hsn": payload_json.get("MainHsnCode"),
                "irn": payload_json.get("Irn"),
                "is_decoded": True,
            }
        except Exception:
            pass

    # Direct JSON fallback if QR is encoded as plain JSON
    try:
        data = json.loads(qr_data_string)
        if isinstance(data, dict):
            return {
                "seller_gstin": data.get("SellerGstin") or data.get("seller_gstin"),
                "buyer_gstin": data.get("BuyerGstin") or data.get("buyer_gstin"),
                "doc_no": data.get("DocNo") or data.get("doc_no"),
                "doc_date": data.get("DocDate") or data.get("doc_date"),
                "total_value": data.get("TotInvVal") or data.get("total_amount"),
                "irn": data.get("Irn") or data.get("irn"),
                "is_decoded": True,
            }
    except Exception:
        pass

    return None


def calculate_iou(box_a: list[float], box_b: list[float]) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.
    Boxes are in format [x0, y0, x1, y1] (either normalized or pixel).
    """
    xa0, ya0, xa1, ya1 = box_a
    xb0, yb0, xb1, yb1 = box_b

    inter_x0 = max(xa0, xb0)
    inter_y0 = max(ya0, yb0)
    inter_x1 = min(xa1, xb1)
    inter_y1 = min(ya1, yb1)

    inter_w = max(0.0, inter_x1 - inter_x0)
    inter_h = max(0.0, inter_y1 - inter_y0)
    inter_area = inter_w * inter_h

    area_a = max(0.0, xa1 - xa0) * max(0.0, ya1 - ya0)
    area_b = max(0.0, xb1 - xb0) * max(0.0, yb1 - yb0)
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return round(inter_area / union_area, 4)
