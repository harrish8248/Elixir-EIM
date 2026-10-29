"""
Generate 120 Synthetic Indian GST Invoices at 300 DPI with Ground Truth Bounding Boxes and e-Invoice QR Codes.
Splits: Train (60), Dev (30), Test (30) with fixed seed 42.
"""

import base64
import json
import math
import os
from pathlib import Path
import random
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import qrcode

from apps.api.app.content.idp.gstin import compute_gstin_check_char, STATE_CODES

OUTPUT_DIR = Path("docs/ocr-benchmark/data_gst")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INDIAN_SUPPLIERS = [
    {"name": "Tata Consultancy Services Ltd", "pan": "AAACT2718E", "state": "27", "city": "Mumbai", "addr": "TCS House, Raveline Street, Fort"},
    {"name": "Infosys Technologies Pvt Ltd", "pan": "AABCI1234F", "state": "29", "city": "Bengaluru", "addr": "Electronics City, Hosur Road"},
    {"name": "Reliance Corporate IT Services", "pan": "AABCR4567G", "state": "27", "city": "Navi Mumbai", "addr": "Reliance Corporate Park, Thane-Belapur Rd"},
    {"name": "Wipro Enterprise Solutions Ltd", "pan": "AAACW8901H", "state": "29", "city": "Bengaluru", "addr": "Doddakannelli, Sarjapur Road"},
    {"name": "HCL Technologies India Ltd", "pan": "AAACH2345J", "state": "07", "city": "New Delhi", "addr": "Plot No 3A, Sector 126, Noida Expressway"},
    {"name": "Larsen & Toubro Infotech Ltd", "pan": "AAACL6789K", "state": "27", "city": "Mumbai", "addr": "L&T House, Ballard Estate"},
    {"name": "Bharti Airtel Enterprise Services", "pan": "AAACB0123L", "state": "07", "city": "New Delhi", "addr": "Airtel Centre, Plot 16, Udyog Vihar"},
    {"name": "CloudScale Networks India Pvt Ltd", "pan": "AAPFU0939F", "state": "27", "city": "Pune", "addr": "Cybercity Magarpatta, Hadapsar"},
]

INDIAN_BUYERS = [
    {"name": "AcroCorp India Private Limited", "pan": "AABCA9876M", "state": "27", "city": "Mumbai", "addr": "One BKC, G Block, Bandra Kurla Complex"},
    {"name": "Apex Global Services India Ltd", "pan": "AABCA5432N", "state": "29", "city": "Bengaluru", "addr": "Prestige Tech Park, Marathahalli-Sarjapur"},
    {"name": "Zenith Logistics Solutions LLP", "pan": "AAFCZ8765P", "state": "07", "city": "New Delhi", "addr": "Barakhamba Road, Connaught Place"},
    {"name": "Bharat Digital Commerce Ltd", "pan": "AAACB4321Q", "state": "36", "city": "Hyderabad", "addr": "HITEC City, Madhapur"},
    {"name": "Godrej Consumer Products Ltd", "pan": "AAACG1122R", "state": "27", "city": "Mumbai", "addr": "Pirojshanagar, Eastern Express Highway"},
    {"name": "Mahindra Industrial Services", "pan": "AAACM3344S", "state": "27", "city": "Mumbai", "addr": "Mahindra Towers, Worli"},
]

BANKS = [
    {"name": "HDFC Bank Ltd", "ifsc": "HDFC0000123", "branch": "Fort Mumbai"},
    {"name": "State Bank of India", "ifsc": "SBIN0001234", "branch": "Industrial Finance"},
    {"name": "ICICI Bank Limited", "ifsc": "ICIC0000456", "branch": "Bandra Kurla Complex"},
    {"name": "Axis Bank Ltd", "ifsc": "UTIB0000789", "branch": "MG Road Bengaluru"},
]

HSN_CATALOG = [
    {"hsn": "998313", "desc": "Information Technology (IT) Consulting & Support Services", "rate": 18.0},
    {"hsn": "998314", "desc": "Internet Telecommunication & Cloud Hosting Bandwidth", "rate": 18.0},
    {"hsn": "998315", "desc": "Enterprise Software Licensing & Annual Maintenance", "rate": 18.0},
    {"hsn": "847130", "desc": "Server Rack Infrastructure Hardware Units", "rate": 18.0},
    {"hsn": "998713", "desc": "Maintenance & Repair of Datacenter Infrastructure", "rate": 18.0},
    {"hsn": "998222", "desc": "Accounting & Auditing Compliance Professional Services", "rate": 18.0},
]


def make_valid_gstin(pan: str, state: str, entity_code: str = "1") -> str:
    first14 = f"{state}{pan}{entity_code}Z"
    check = compute_gstin_check_char(first14)
    return f"{first14}{check}"


def num_to_words_inr(num: float) -> str:
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
             "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    n = int(round(num))
    if n == 0:
        return "Zero"

    def two_digits(val: int) -> str:
        if val < 20:
            return units[val]
        else:
            return tens[val // 10] + (" " + units[val % 10] if val % 10 else "")

    parts = []
    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    hundred = n // 100
    rem = n % 100

    if crore:
        parts.append(two_digits(crore) + " Crore")
    if lakh:
        parts.append(two_digits(lakh) + " Lakh")
    if thousand:
        parts.append(two_digits(thousand) + " Thousand")
    if hundred:
        parts.append(units[hundred] + " Hundred")
    if rem:
        parts.append(two_digits(rem))

    return "INR " + " ".join(parts) + " Only"


def draw_indian_gst_invoice(inv_idx: int, seed: int) -> tuple[Image.Image, dict]:
    random.seed(seed)
    W, H = 2550, 3300
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        f_title = ImageFont.truetype("arialbd.ttf", 46)
        f_sub = ImageFont.truetype("arial.ttf", 26)
        f_h2 = ImageFont.truetype("arialbd.ttf", 32)
        f_body_b = ImageFont.truetype("arialbd.ttf", 26)
        f_body = ImageFont.truetype("arial.ttf", 24)
        f_small = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        f_title = ImageFont.load_default()
        f_sub = f_title
        f_h2 = f_title
        f_body_b = f_title
        f_body = f_title
        f_small = f_title

    supplier = random.choice(INDIAN_SUPPLIERS)
    buyer = random.choice(INDIAN_BUYERS)
    bank = random.choice(BANKS)

    supplier_gstin = make_valid_gstin(supplier["pan"], supplier["state"])
    buyer_gstin = make_valid_gstin(buyer["pan"], buyer["state"])

    inv_num = f"GST-{random.randint(2026, 2027)}-{inv_idx+1000:04d}"
    inv_date = f"2026-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    due_date = f"2026-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"

    # Place of supply
    is_intra_state = supplier["state"] == buyer["state"]
    pos_state = buyer["state"]
    pos_name = STATE_CODES.get(pos_state, "Maharashtra")

    # Line items
    num_items = random.randint(2, 4)
    items = []
    taxable_val = 0.0
    for idx in range(num_items):
        cat = random.choice(HSN_CATALOG)
        qty = random.randint(1, 10)
        rate = float(random.choice([2500, 5000, 12000, 18500, 35000, 60000]))
        line_taxable = round(qty * rate, 2)
        taxable_val += line_taxable
        items.append({
            "sl": idx + 1,
            "hsn": cat["hsn"],
            "desc": cat["desc"],
            "qty": qty,
            "rate": rate,
            "taxable": line_taxable,
            "tax_pct": cat["rate"],
        })

    taxable_val = round(taxable_val, 2)
    if is_intra_state:
        cgst_val = round(taxable_val * 0.09, 2)
        sgst_val = round(taxable_val * 0.09, 2)
        igst_val = 0.0
    else:
        cgst_val = 0.0
        sgst_val = 0.0
        igst_val = round(taxable_val * 0.18, 2)

    total_val = round(taxable_val + cgst_val + sgst_val + igst_val, 2)
    words_amt = num_to_words_inr(total_val)
    irn = f"{random.randint(10**63, 10**64 - 1):064x}"[:64]

    # Generate QR Code
    qr_payload = {
        "SellerGstin": supplier_gstin,
        "BuyerGstin": buyer_gstin,
        "DocNo": inv_num,
        "DocDate": inv_date,
        "TotInvVal": total_val,
        "ItemCnt": num_items,
        "MainHsnCode": items[0]["hsn"],
        "Irn": irn,
    }
    jwt_payload_str = base64.urlsafe_b64encode(json.dumps(qr_payload).encode("utf-8")).decode("utf-8").rstrip("=")
    fake_jwt = f"eyJhbGciOiJSUzI1NiJ9.{jwt_payload_str}.signed_irn_token"

    qr = qrcode.QRCode(box_size=3, border=4)
    qr.add_data(fake_jwt)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Render Document Header
    draw.rectangle([100, 100, W - 100, H - 100], outline=(40, 40, 40), width=4)

    # Title Banner
    draw.rectangle([100, 100, W - 100, 220], fill=(240, 244, 250), outline=(40, 40, 40), width=3)
    draw.text((W // 2 - 250, 135), "TAX INVOICE / GST INVOICE", fill=(20, 30, 60), font=f_title)
    draw.text((W // 2 - 200, 185), "(Issued under Section 31 of CGST Act, 2017)", fill=(100, 100, 100), font=f_small)

    # Embed QR Code at Top Right (fits cleanly above y=500)
    qr_w, qr_h = qr_img.size
    qr_x, qr_y = W - 140 - qr_w, 230
    img.paste(qr_img, (qr_x, qr_y))
    draw.text((qr_x, qr_y + qr_h + 4), "IRN Verified e-Invoice", fill=(80, 80, 80), font=f_small)

    boxes: dict[str, list[float]] = {}
    boxes["irn_qr_code"] = [round(qr_x / W, 4), round(qr_y / H, 4), round((qr_x + qr_w) / W, 4), round((qr_y + qr_h) / H, 4)]

    def to_norm(tb):
        return [round(tb[0] / W, 4), round(tb[1] / H, 4), round(tb[2] / W, 4), round(tb[3] / H, 4)]

    # Supplier Details (Left)
    y = 250
    draw.text((130, y), supplier["name"], fill=(15, 25, 50), font=f_h2)
    boxes["supplier_name"] = to_norm(draw.textbbox((130, y), supplier["name"], font=f_h2))
    y += 45
    draw.text((130, y), f"{supplier['addr']}, {supplier['city']} - {supplier['state']}", fill=(60, 60, 60), font=f_sub)
    y += 40

    draw.text((130, y), "GSTIN:", fill=(20, 20, 20), font=f_body_b)
    draw.text((230, y), supplier_gstin, fill=(20, 35, 90), font=f_body_b)
    boxes["supplier_gstin"] = to_norm(draw.textbbox((230, y), supplier_gstin, font=f_body_b))
    y += 35

    draw.text((130, y), f"PAN: {supplier['pan']}  |  State: {STATE_CODES.get(supplier['state'], '')} (Code: {supplier['state']})", fill=(60, 60, 60), font=f_body)
    boxes["supplier_pan"] = to_norm(draw.textbbox((180, y), supplier["pan"], font=f_body))
    y += 50

    # Invoice Meta Box (Below supplier and QR)
    draw.line([100, 500, W - 100, 500], fill=(40, 40, 40), width=3)
    draw.rectangle([100, 500, W - 100, 620], fill=(248, 250, 252))

    draw.text((130, 520), "Invoice Number:", fill=(70, 70, 70), font=f_body)
    draw.text((340, 520), inv_num, fill=(20, 20, 20), font=f_body_b)
    boxes["invoice_number"] = to_norm(draw.textbbox((340, 520), inv_num, font=f_body_b))

    draw.text((800, 520), "Invoice Date:", fill=(70, 70, 70), font=f_body)
    draw.text((980, 520), inv_date, fill=(20, 20, 20), font=f_body_b)
    boxes["invoice_date"] = to_norm(draw.textbbox((980, 520), inv_date, font=f_body_b))

    draw.text((130, 570), "Place of Supply:", fill=(70, 70, 70), font=f_body)
    draw.text((340, 570), f"{pos_name} ({pos_state})", fill=(20, 20, 20), font=f_body_b)
    boxes["place_of_supply"] = to_norm(draw.textbbox((340, 570), f"{pos_name} ({pos_state})", font=f_body_b))

    draw.text((800, 570), "Due Date:", fill=(70, 70, 70), font=f_body)
    draw.text((980, 570), due_date, fill=(20, 20, 20), font=f_body)

    # Buyer / Recipient Details Box
    draw.line([100, 620, W - 100, 620], fill=(40, 40, 40), width=3)
    draw.rectangle([100, 620, W - 100, 800], fill=(255, 255, 255))
    draw.text((130, 635), "Details of Receiver / Billed To:", fill=(100, 100, 100), font=f_small)

    draw.text((130, 665), buyer["name"], fill=(20, 30, 60), font=f_h2)
    boxes["buyer_name"] = to_norm(draw.textbbox((130, 665), buyer["name"], font=f_h2))

    draw.text((130, 710), f"{buyer['addr']}, {buyer['city']} - State: {pos_name} ({pos_state})", fill=(60, 60, 60), font=f_body)

    draw.text((130, 750), "GSTIN:", fill=(20, 20, 20), font=f_body_b)
    draw.text((230, 750), buyer_gstin, fill=(20, 35, 90), font=f_body_b)
    boxes["buyer_gstin"] = to_norm(draw.textbbox((230, 750), buyer_gstin, font=f_body_b))

    draw.text((650, 750), f"PAN: {buyer['pan']}", fill=(60, 60, 60), font=f_body)
    boxes["buyer_pan"] = to_norm(draw.textbbox((710, 750), buyer["pan"], font=f_body))

    # HSN / Items Table Header
    draw.line([100, 800, W - 100, 800], fill=(40, 40, 40), width=3)
    draw.rectangle([100, 800, W - 100, 860], fill=(235, 240, 248))
    headers = [("Sl", 120), ("HSN/SAC", 190), ("Description of Goods / Services", 380), ("Qty", 1450), ("Rate", 1600), ("Taxable Amt (INR)", 1820), ("Total (INR)", 2180)]
    for htitle, hx in headers:
        draw.text((hx, 818), htitle, fill=(20, 30, 60), font=f_body_b)

    draw.line([100, 860, W - 100, 860], fill=(40, 40, 40), width=2)

    # Items Rows
    item_y = 880
    for it in items:
        draw.text((125, item_y), str(it["sl"]), fill=(40, 40, 40), font=f_body)
        draw.text((190, item_y), it["hsn"], fill=(40, 40, 40), font=f_body)
        draw.text((380, item_y), it["desc"][:45], fill=(40, 40, 40), font=f_body)
        draw.text((1460, item_y), str(it["qty"]), fill=(40, 40, 40), font=f_body)
        draw.text((1600, item_y), f"{it['rate']:,.2f}", fill=(40, 40, 40), font=f_body)
        draw.text((1850, item_y), f"{it['taxable']:,.2f}", fill=(40, 40, 40), font=f_body)
        line_tot = it["taxable"] * (1.0 + it["tax_pct"] / 100.0)
        draw.text((2200, item_y), f"{line_tot:,.2f}", fill=(40, 40, 40), font=f_body)
        item_y += 55

    # Tax Summary Box
    sum_y = max(item_y + 40, 1200)
    draw.line([100, sum_y, W - 100, sum_y], fill=(40, 40, 40), width=3)
    draw.rectangle([W - 1100, sum_y, W - 100, sum_y + 260], fill=(250, 252, 255), outline=(180, 180, 180), width=2)

    sy = sum_y + 15
    draw.text((W - 1050, sy), "Total Taxable Value:", fill=(50, 50, 50), font=f_body)
    draw.text((W - 400, sy), f"{taxable_val:,.2f}", fill=(20, 20, 20), font=f_body_b)
    boxes["taxable_value"] = to_norm(draw.textbbox((W - 400, sy), f"{taxable_val:,.2f}", font=f_body_b))
    sy += 40

    if is_intra_state:
        draw.text((W - 1050, sy), "Central GST (CGST @ 9%):", fill=(50, 50, 50), font=f_body)
        draw.text((W - 400, sy), f"{cgst_val:,.2f}", fill=(20, 20, 20), font=f_body)
        boxes["cgst"] = to_norm(draw.textbbox((W - 400, sy), f"{cgst_val:,.2f}", font=f_body))
        sy += 38

        draw.text((W - 1050, sy), "State GST (SGST @ 9%):", fill=(50, 50, 50), font=f_body)
        draw.text((W - 400, sy), f"{sgst_val:,.2f}", fill=(20, 20, 20), font=f_body)
        boxes["sgst"] = to_norm(draw.textbbox((W - 400, sy), f"{sgst_val:,.2f}", font=f_body))
        sy += 38
        boxes["igst"] = [0.0, 0.0, 0.0, 0.0]
    else:
        draw.text((W - 1050, sy), "Integrated GST (IGST @ 18%):", fill=(50, 50, 50), font=f_body)
        draw.text((W - 400, sy), f"{igst_val:,.2f}", fill=(20, 20, 20), font=f_body)
        boxes["igst"] = to_norm(draw.textbbox((W - 400, sy), f"{igst_val:,.2f}", font=f_body))
        sy += 38
        boxes["cgst"] = [0.0, 0.0, 0.0, 0.0]
        boxes["sgst"] = [0.0, 0.0, 0.0, 0.0]

    draw.line([W - 1100, sy, W - 100, sy], fill=(40, 40, 40), width=2)
    sy += 12
    draw.text((W - 1050, sy), "Total Invoice Value (INR):", fill=(20, 30, 70), font=f_h2)
    draw.text((W - 420, sy), f"₹ {total_val:,.2f}", fill=(20, 30, 90), font=f_h2)
    boxes["total_amount"] = to_norm(draw.textbbox((W - 420, sy), f"₹ {total_val:,.2f}", font=f_h2))

    # Bank Details Box & Amount in Words (Left side below table)
    by = sum_y + 20
    draw.text((130, by), "Amount Chargeable in Words:", fill=(100, 100, 100), font=f_small)
    by += 30
    draw.text((130, by), words_amt, fill=(20, 20, 20), font=f_body_b)
    boxes["amount_in_words"] = to_norm(draw.textbbox((130, by), words_amt, font=f_body_b))
    by += 60

    draw.text((130, by), "Bank Remittance Details:", fill=(100, 100, 100), font=f_small)
    by += 30
    draw.text((130, by), f"Bank Name: {bank['name']}", fill=(40, 40, 40), font=f_body)
    boxes["bank_name"] = to_norm(draw.textbbox((130, by), f"Bank Name: {bank['name']}", font=f_body))
    by += 35
    acct = f"9876543210{inv_idx:04d}"
    draw.text((130, by), "A/C Number:", fill=(40, 40, 40), font=f_body)
    draw.text((280, by), acct, fill=(20, 20, 20), font=f_body_b)
    boxes["bank_account"] = to_norm(draw.textbbox((280, by), acct, font=f_body_b))

    draw.text((600, by), "IFSC:", fill=(40, 40, 40), font=f_body)
    draw.text((700, by), bank["ifsc"], fill=(20, 20, 20), font=f_body_b)
    boxes["bank_ifsc"] = to_norm(draw.textbbox((700, by), bank["ifsc"], font=f_body_b))

    # IRN text string footer
    draw.line([100, H - 260, W - 100, H - 260], fill=(200, 200, 200), width=2)
    draw.text((130, H - 235), f"IRN: {irn}", fill=(110, 110, 110), font=f_small)
    draw.text((130, H - 200), "This is a computer-generated digitally signed invoice under Rule 48(4) of CGST Rules.", fill=(130, 130, 130), font=f_small)

    meta = {
        "invoice_number": inv_num,
        "invoice_date": inv_date,
        "due_date": due_date,
        "supplier_name": supplier["name"],
        "supplier_gstin": supplier_gstin,
        "supplier_pan": supplier["pan"],
        "buyer_name": buyer["name"],
        "buyer_gstin": buyer_gstin,
        "buyer_pan": buyer["pan"],
        "place_of_supply": f"{pos_name} ({pos_state})",
        "taxable_value": taxable_val,
        "cgst": cgst_val,
        "sgst": sgst_val,
        "igst": igst_val,
        "cess": 0.0,
        "total_amount": total_val,
        "amount_in_words": words_amt,
        "bank_name": bank["name"],
        "bank_account": acct,
        "bank_ifsc": bank["ifsc"],
        "irn": irn,
        "is_intra_state": is_intra_state,
        "field_boxes": boxes,
        "items": items,
    }
    return img, meta


def degrade_gst_invoice(img: Image.Image, deg_type: str, seed: int) -> Image.Image:
    random.seed(seed)
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = cv_img.shape[:2]

    if deg_type == "skew":
        angle = random.choice([-2.5, -1.8, 1.8, 2.5])
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        cv_img = cv2.warpAffine(cv_img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    elif deg_type == "blur":
        k = random.choice([3, 5])
        cv_img = cv2.GaussianBlur(cv_img, (k, k), 0)
    elif deg_type == "noise":
        noise = np.random.normal(0, 14, cv_img.shape).astype(np.float32)
        cv_img = np.clip(cv_img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    elif deg_type == "contrast":
        alpha = 0.55
        beta = 45
        cv_img = np.clip(alpha * cv_img + beta, 0, 255).astype(np.uint8)
    elif deg_type == "rotated_90":
        cv_img = cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE)
    elif deg_type == "compression":
        _, enc = cv2.imencode(".jpg", cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), 35])
        cv_img = cv2.imdecode(enc, 1)

    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))


def main():
    print("Generating 120 Synthetic Indian GST Invoices at 300 DPI...", flush=True)
    all_records = []
    deg_types = ["skew", "blur", "noise", "contrast", "rotated_90", "compression"]

    # 60 clean invoices, 60 degraded invoices = 120 total
    for i in range(120):
        is_deg = i >= 60
        deg_kind = deg_types[(i - 60) % len(deg_types)] if is_deg else "clean"
        seed = 42 + i * 17

        img, meta = draw_indian_gst_invoice(i, seed)
        if is_deg:
            img = degrade_gst_invoice(img, deg_kind, seed)

        tag = f"gst_{i:03d}_{'deg_' + deg_kind if is_deg else 'clean'}"
        img_p = OUTPUT_DIR / f"{tag}.png"
        json_p = OUTPUT_DIR / f"{tag}.json"

        img.save(img_p, format="PNG")
        meta["image_path"] = str(img_p).replace("\\", "/")
        meta["is_degraded"] = is_deg
        meta["degradation_type"] = deg_kind
        meta["document_type"] = "invoice_gst"

        with open(json_p, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        all_records.append({
            "id": tag,
            "image_path": str(img_p).replace("\\", "/"),
            "json_path": str(json_p).replace("\\", "/"),
            "is_degraded": is_deg,
            "degradation_type": deg_kind,
        })

    # Fixed seed 42 split: Train (60), Dev (30), Test (30)
    # Stratified: Clean vs Degraded 50/50 in every split
    clean_recs = [r for r in all_records if not r["is_degraded"]]
    deg_recs = [r for r in all_records if r["is_degraded"]]

    random.seed(42)
    random.shuffle(clean_recs)
    random.shuffle(deg_recs)

    train_recs = clean_recs[:30] + deg_recs[:30]
    dev_recs = clean_recs[30:45] + deg_recs[30:45]
    test_recs = clean_recs[45:60] + deg_recs[45:60]

    splits = {
        "train": [r["id"] for r in train_recs],
        "dev": [r["id"] for r in dev_recs],
        "test": [r["id"] for r in test_recs],
    }

    with open(OUTPUT_DIR / "splits_gst.json", "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2)

    print(f"Successfully generated 120 Indian GST invoices in {OUTPUT_DIR}:", flush=True)
    print(f"  Train Split: {len(splits['train'])} documents (30 clean, 30 degraded)")
    print(f"  Dev Split:   {len(splits['dev'])} documents (15 clean, 15 degraded)")
    print(f"  Test Split:  {len(splits['test'])} documents (15 clean, 15 degraded)")


if __name__ == "__main__":
    main()
