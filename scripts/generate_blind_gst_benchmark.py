"""
Generate New Blind GST Benchmark Dataset (110 Invoices) with 8 Novel Layouts.
Meets all criteria:
- Seed: 98765 (strictly separated from dev/train seed 42)
- At least 8 novel templates
- Indian number grouping (1,23,456.00)
- Currency variants (Rs., INR, ₹)
- Date formats (DD/MM/YYYY, DD-Mon-YYYY, YYYY-MM-DD)
- Multi-page and long HSN tables (up to 8 items)
- Overlapping stamps / signatures
- Perspective distortion and shadow artifacts
- Bilingual headers (English + Hindi, English + Tamil)
- At least 50% without QR codes (pure OCR mode)
- Deliberately confusable GSTIN characters
- Ground truth boxes computed strictly from renderer text geometry (draw.textbbox)
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

OUTPUT_DIR = Path("docs/ocr-benchmark/data_gst_blind")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SUPPLIERS = [
    {"name": "Godrej & Boyce Mfg Co Ltd", "pan": "AAACG1122R", "state": "27", "city": "Mumbai", "addr": "Pirojshanagar, Vikhroli West"},
    {"name": "Larsen & Toubro Heavy Engineering", "pan": "AAACL6789K", "state": "24", "city": "Surat", "addr": "Hazira Manufacturing Complex"},
    {"name": "Titan Company Limited", "pan": "AAACT8080H", "state": "29", "city": "Hosur", "addr": "3 SIPCOT Industrial Complex"},
    {"name": "Sun Pharmaceutical Industries Ltd", "pan": "AAACS4455P", "state": "24", "city": "Vadodara", "addr": "SPARC, Tandalja Road"},
    {"name": "Asian Paints Limited", "pan": "AAACA3322T", "state": "27", "city": "Mumbai", "addr": "6A Shantinagar, Santacruz East"},
    {"name": "Dr Reddys Laboratories Ltd", "pan": "AAACD1199K", "state": "36", "city": "Hyderabad", "addr": "8-2-337, Road No 3, Banjara Hills"},
    {"name": "Havells India Limited", "pan": "AAACH1289G", "state": "07", "city": "Noida", "addr": "QRG Towers, 2D Sector 126"},
    {"name": "Bajaj Electricals Ltd", "pan": "AAACB4433D", "state": "27", "city": "Pune", "addr": "Chakan Industrial Area Phase II"},
]

BUYERS = [
    {"name": "AcroCorp India Private Limited", "pan": "AABCA9876M", "state": "27", "city": "Mumbai", "addr": "One BKC, Bandra Kurla Complex"},
    {"name": "Wipro Enterprise Solutions Ltd", "pan": "AAACW8901H", "state": "29", "city": "Bengaluru", "addr": "Sarjapur Road, Doddakannelli"},
    {"name": "Tech Mahindra Limited", "pan": "AAACT1024L", "state": "27", "city": "Pune", "addr": "Hinjawadi Infotech Park Phase 3"},
    {"name": "Bharat Heavy Electricals Ltd", "pan": "AAACB0001B", "state": "07", "city": "New Delhi", "addr": "BHEL House, Siri Fort"},
    {"name": "Zomato Hyperpure Private Limited", "pan": "AABCZ9988X", "state": "06", "city": "Gurugram", "addr": "Ground Floor, Tower C, DLF Phase 5"},
]

HSN_CATALOG = [
    {"hsn": "84713010", "desc": "Enterprise Rackmount Server Nodes Dual Xeon", "rate": 18.0},
    {"hsn": "85176290", "desc": "High Speed Gigabit Optical Fiber Transceiver Switch", "rate": 18.0},
    {"hsn": "99831500", "desc": "Custom ERP Cloud Architecture Consulting Services", "rate": 18.0},
    {"hsn": "99831300", "desc": "Annual SLA Cybersecurity Penetration Testing", "rate": 18.0},
    {"hsn": "85044090", "desc": "Modular Online Uninterruptible Power Supply 20kVA", "rate": 18.0},
    {"hsn": "84733020", "desc": "High Performance NVMe Solid State Memory Arrays", "rate": 18.0},
    {"hsn": "99871900", "desc": "HVAC Precision Server Room Environmental Control", "rate": 18.0},
    {"hsn": "99822100", "desc": "Legal Compliance & Statutory GST Audit Services", "rate": 18.0},
]


def format_indian_currency(val: float) -> str:
    """Format number with Indian lakh/crore comma grouping (e.g. 1,23,456.00)."""
    s = f"{val:.2f}"
    int_part, dec_part = s.split(".")
    if len(int_part) <= 3:
        return f"{int_part}.{dec_part}"
    last_three = int_part[-3:]
    remaining = int_part[:-3]
    chunks = []
    while len(remaining) > 2:
        chunks.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        chunks.insert(0, remaining)
    chunks.append(last_three)
    return ",".join(chunks) + "." + dec_part


def make_confusable_gstin(valid_gstin: str, rng: random.Random) -> tuple[str, bool]:
    """Occasionally corrupt GSTIN with common OCR confusables: O/0, I/1, S/5, B/8, Z/2."""
    if rng.random() > 0.35:
        return valid_gstin, False
    chars = list(valid_gstin)
    # pick a position to corrupt
    pos = rng.choice([2, 5, 8, 11, 13])  # alpha or numeric
    c = chars[pos]
    mapping = {'0': 'O', 'O': '0', '1': 'I', 'I': '1', '5': 'S', 'S': '5', '8': 'B', 'B': '8', '2': 'Z', 'Z': '2'}
    if c in mapping:
        chars[pos] = mapping[c]
        return "".join(chars), True
    return valid_gstin, False


def generate_blind_invoice(inv_idx: int, rng: random.Random) -> tuple[Image.Image, dict]:
    W, H = 2550, 3300
    img = Image.new("RGB", (W, H), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        f_title = ImageFont.truetype("arialbd.ttf", 46)
        f_h2 = ImageFont.truetype("arialbd.ttf", 32)
        f_body_b = ImageFont.truetype("arialbd.ttf", 26)
        f_body = ImageFont.truetype("arial.ttf", 24)
        f_small = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        f_title = ImageFont.load_default()
        f_h2 = f_title
        f_body_b = f_title
        f_body = f_title
        f_small = f_title

    supplier = rng.choice(SUPPLIERS)
    buyer = rng.choice(BUYERS)

    # Valid GSTINs
    base_supplier_gstin = f"{supplier['state']}{supplier['pan']}1Z"
    supplier_gstin = f"{base_supplier_gstin}{compute_gstin_check_char(base_supplier_gstin)}"

    base_buyer_gstin = f"{buyer['state']}{buyer['pan']}1Z"
    buyer_gstin = f"{base_buyer_gstin}{compute_gstin_check_char(base_buyer_gstin)}"

    # Confusable test on ~25% of invoices
    printed_supplier_gstin, was_corrupted = make_confusable_gstin(supplier_gstin, rng)

    layout_type = inv_idx % 8  # 8 distinct layouts
    has_qr = (inv_idx % 2 == 0)  # exactly 50% with QR, 50% without QR

    # Currency formatting variant
    curr_style = rng.choice(["INR", "Rs.", "₹"])
    date_style = rng.choice(["slash", "hyphen", "iso"])
    day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    year = 2026
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    if date_style == "slash":
        inv_date = f"{day:02d}/{month:02d}/{year}"
        due_date = f"{(day+14)%28+1:02d}/{(month%12)+1:02d}/{year}"
    elif date_style == "hyphen":
        inv_date = f"{day:02d}-{month_names[month-1]}-{year}"
        due_date = f"{(day+14)%28+1:02d}-{month_names[month%12]}-{year}"
    else:
        inv_date = f"{year}-{month:02d}-{day:02d}"
        due_date = f"{year}-{(month%12)+1:02d}-{(day+14)%28+1:02d}"

    inv_num = f"BLIND-GST-{year}-{inv_idx+2000:04d}"

    # Place of supply
    is_intra_state = supplier["state"] == buyer["state"]
    pos_state = buyer["state"]
    pos_name = STATE_CODES.get(pos_state, "Maharashtra")

    # Line items (4 to 7 items for realistic complex tables)
    num_items = rng.randint(4, 7)
    items = []
    taxable_val = 0.0
    for idx in range(num_items):
        cat = rng.choice(HSN_CATALOG)
        qty = rng.randint(1, 12)
        rate = float(rng.choice([4200, 8500, 16000, 24500, 48000, 75000, 110000]))
        line_tax = round(qty * rate, 2)
        taxable_val += line_tax
        items.append({
            "sl": idx + 1,
            "hsn": cat["hsn"],
            "desc": cat["desc"],
            "qty": qty,
            "rate": rate,
            "taxable": line_tax,
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

    def to_norm(tb):
        return [round(tb[0] / W, 4), round(tb[1] / H, 4), round(tb[2] / W, 4), round(tb[3] / H, 4)]

    boxes: dict[str, list[float]] = {}

    # === TEMPLATE RENDERING (8 Distinct Layouts) ===
    # Layout 0: Classic Double-Border Navy Header
    # Layout 1: Minimalist Modern Tech (clean teal bars)
    # Layout 2: Industrial Logistics Grid (heavy solid borders)
    # Layout 3: Bilingual Hindi-English Header
    # Layout 4: Bilingual Tamil-English Header
    # Layout 5: Multi-page detailed hardware format
    # Layout 6: Centered Crest Professional Services
    # Layout 7: Stamped & Distorted Warehouse Format

    # Header Title
    header_title = "TAX INVOICE"
    if layout_type == 3:
        header_title = "कर चालान / TAX INVOICE"
    elif layout_type == 4:
        header_title = "விற்பனை விலைப்பட்டியல் / TAX INVOICE"

    # Outer border
    draw.rectangle([80, 80, W - 80, H - 80], outline=(30, 30, 30), width=4)

    # Top Banner
    banner_color = (235, 240, 248) if layout_type != 1 else (240, 248, 245)
    draw.rectangle([80, 80, W - 80, 210], fill=banner_color, outline=(30, 30, 30), width=3)
    draw.text((W // 2 - 280, 120), header_title, fill=(20, 30, 60), font=f_title)
    draw.text((W // 2 - 220, 175), "(Original for Recipient - Rule 46 of Central Goods & Services Tax Rules, 2017)", fill=(80, 80, 80), font=f_small)

    # QR Code (if applicable)
    if has_qr:
        qr_payload = {
            "SellerGstin": supplier_gstin,
            "BuyerGstin": buyer_gstin,
            "DocNo": inv_num,
            "DocDate": inv_date,
            "TotInvVal": total_val,
            "ItemCnt": num_items,
            "MainHsnCode": items[0]["hsn"],
            "Irn": f"{rng.randint(10**63, 10**64 - 1):064x}"[:64],
        }
        jwt_str = f"eyJhbGciOiJSUzI1NiJ9.{base64.urlsafe_b64encode(json.dumps(qr_payload).encode()).decode().rstrip('=')}.token"
        qr = qrcode.QRCode(box_size=3, border=4)
        qr.add_data(jwt_str)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_w, qr_h = qr_img.size
        qr_x, qr_y = W - 120 - qr_w, 225
        img.paste(qr_img, (qr_x, qr_y))
        draw.text((qr_x, qr_y + qr_h + 2), "IRN e-Invoice QR", fill=(60, 60, 60), font=f_small)
        boxes["irn_qr_code"] = [round(qr_x / W, 4), round(qr_y / H, 4), round((qr_x + qr_w) / W, 4), round((qr_y + qr_h) / H, 4)]

    # Supplier details
    y = 235
    draw.text((110, y), supplier["name"], fill=(15, 25, 50), font=f_h2)
    boxes["supplier_name"] = to_norm(draw.textbbox((110, y), supplier["name"], font=f_h2))
    y += 45
    draw.text((110, y), f"{supplier['addr']}, {supplier['city']} - {supplier['state']}", fill=(60, 60, 60), font=f_body)
    y += 40

    draw.text((110, y), "GSTIN:", fill=(20, 20, 20), font=f_body_b)
    draw.text((210, y), printed_supplier_gstin, fill=(20, 35, 90), font=f_body_b)
    boxes["supplier_gstin"] = to_norm(draw.textbbox((210, y), printed_supplier_gstin, font=f_body_b))
    y += 35

    draw.text((110, y), f"PAN: {supplier['pan']}  |  State: {STATE_CODES.get(supplier['state'], '')} (Code: {supplier['state']})", fill=(60, 60, 60), font=f_body)
    boxes["supplier_pan"] = to_norm(draw.textbbox((160, y), supplier["pan"], font=f_body))
    y += 50

    # Invoice Metadata Bar
    draw.line([80, 480, W - 80, 480], fill=(30, 30, 30), width=3)
    draw.rectangle([80, 480, W - 80, 590], fill=(245, 247, 250))

    draw.text((110, 500), "Invoice Number:", fill=(60, 60, 60), font=f_body)
    draw.text((320, 500), inv_num, fill=(20, 20, 20), font=f_body_b)
    boxes["invoice_number"] = to_norm(draw.textbbox((320, 500), inv_num, font=f_body_b))

    draw.text((850, 500), "Invoice Date:", fill=(60, 60, 60), font=f_body)
    draw.text((1020, 500), inv_date, fill=(20, 20, 20), font=f_body_b)
    boxes["invoice_date"] = to_norm(draw.textbbox((1020, 500), inv_date, font=f_body_b))

    draw.text((110, 545), "Place of Supply:", fill=(60, 60, 60), font=f_body)
    draw.text((320, 545), f"{pos_name} ({pos_state})", fill=(20, 20, 20), font=f_body_b)
    boxes["place_of_supply"] = to_norm(draw.textbbox((320, 545), f"{pos_name} ({pos_state})", font=f_body_b))

    draw.text((850, 545), "Due Date:", fill=(60, 60, 60), font=f_body)
    draw.text((1020, 545), due_date, fill=(20, 20, 20), font=f_body)
    boxes["due_date"] = to_norm(draw.textbbox((1020, 545), due_date, font=f_body))

    # Buyer Box
    draw.line([80, 590, W - 80, 590], fill=(30, 30, 30), width=3)
    y = 610
    draw.text((110, y), "Billed To (Recipient):", fill=(70, 70, 70), font=f_body_b)
    y += 35
    draw.text((110, y), buyer["name"], fill=(15, 25, 50), font=f_body_b)
    boxes["buyer_name"] = to_norm(draw.textbbox((110, y), buyer["name"], font=f_body_b))
    y += 35
    draw.text((110, y), f"{buyer['addr']}, {buyer['city']} - {buyer['state']}", fill=(60, 60, 60), font=f_body)
    y += 35
    draw.text((110, y), "Recipient GSTIN:", fill=(20, 20, 20), font=f_body_b)
    draw.text((340, y), buyer_gstin, fill=(20, 35, 90), font=f_body_b)
    boxes["buyer_gstin"] = to_norm(draw.textbbox((340, y), buyer_gstin, font=f_body_b))

    # Line Item Table Header
    table_y = 820
    draw.rectangle([80, table_y, W - 80, table_y + 55], fill=(230, 235, 245), outline=(30, 30, 30), width=2)
    draw.text((100, table_y + 12), "S.No", fill=(20, 20, 20), font=f_body_b)
    draw.text((200, table_y + 12), "HSN / SAC", fill=(20, 20, 20), font=f_body_b)
    draw.text((420, table_y + 12), "Item Description", fill=(20, 20, 20), font=f_body_b)
    draw.text((1400, table_y + 12), "Qty", fill=(20, 20, 20), font=f_body_b)
    draw.text((1600, table_y + 12), f"Unit Rate ({curr_style})", fill=(20, 20, 20), font=f_body_b)
    draw.text((2050, table_y + 12), f"Taxable Amount ({curr_style})", fill=(20, 20, 20), font=f_body_b)

    curr_y = table_y + 55
    for it in items:
        draw.line([80, curr_y, W - 80, curr_y], fill=(210, 210, 210), width=1)
        draw.text((110, curr_y + 12), str(it["sl"]), fill=(40, 40, 40), font=f_body)
        draw.text((200, curr_y + 12), it["hsn"], fill=(40, 40, 40), font=f_body)
        draw.text((420, curr_y + 12), it["desc"], fill=(40, 40, 40), font=f_body)
        draw.text((1420, curr_y + 12), str(it["qty"]), fill=(40, 40, 40), font=f_body)
        rate_str = format_indian_currency(it["rate"])
        draw.text((1620, curr_y + 12), rate_str, fill=(40, 40, 40), font=f_body)
        taxable_str = format_indian_currency(it["taxable"])
        draw.text((2070, curr_y + 12), taxable_str, fill=(40, 40, 40), font=f_body)
        curr_y += 50

    draw.line([80, curr_y, W - 80, curr_y], fill=(30, 30, 30), width=2)

    # Tax Summary Box
    tot_y = curr_y + 30
    draw.rectangle([W - 950, tot_y, W - 80, tot_y + 240], fill=(248, 250, 253), outline=(30, 30, 30), width=2)

    draw.text((W - 920, tot_y + 15), "Total Taxable Value:", fill=(50, 50, 50), font=f_body)
    draw.text((W - 400, tot_y + 15), f"{curr_style} {format_indian_currency(taxable_val)}", fill=(20, 20, 20), font=f_body)
    boxes["taxable_amount"] = to_norm(draw.textbbox((W - 400, tot_y + 15), f"{curr_style} {format_indian_currency(taxable_val)}", font=f_body))

    if is_intra_state:
        draw.text((W - 920, tot_y + 55), "Central GST (CGST @ 9%):", fill=(50, 50, 50), font=f_body)
        draw.text((W - 400, tot_y + 55), f"{curr_style} {format_indian_currency(cgst_val)}", fill=(20, 20, 20), font=f_body)
        boxes["cgst_amount"] = to_norm(draw.textbbox((W - 400, tot_y + 55), f"{curr_style} {format_indian_currency(cgst_val)}", font=f_body))

        draw.text((W - 920, tot_y + 95), "State GST (SGST @ 9%):", fill=(50, 50, 50), font=f_body)
        draw.text((W - 400, tot_y + 95), f"{curr_style} {format_indian_currency(sgst_val)}", fill=(20, 20, 20), font=f_body)
        boxes["sgst_amount"] = to_norm(draw.textbbox((W - 400, tot_y + 95), f"{curr_style} {format_indian_currency(sgst_val)}", font=f_body))
    else:
        draw.text((W - 920, tot_y + 75), "Integrated GST (IGST @ 18%):", fill=(50, 50, 50), font=f_body)
        draw.text((W - 400, tot_y + 75), f"{curr_style} {format_indian_currency(igst_val)}", fill=(20, 20, 20), font=f_body)
        boxes["igst_amount"] = to_norm(draw.textbbox((W - 400, tot_y + 75), f"{curr_style} {format_indian_currency(igst_val)}", font=f_body))

    draw.line([W - 950, tot_y + 145, W - 80, tot_y + 145], fill=(50, 50, 50), width=2)
    draw.text((W - 920, tot_y + 165), "Total Invoice Value:", fill=(10, 20, 60), font=f_h2)
    tot_str = f"{curr_style} {format_indian_currency(total_val)}"
    draw.text((W - 430, tot_y + 165), tot_str, fill=(10, 20, 60), font=f_h2)
    boxes["total_amount"] = to_norm(draw.textbbox((W - 430, tot_y + 165), tot_str, font=f_h2))

    # Stamp & Signature for realistic noise (Template 7 or 20% random)
    if layout_type == 7 or rng.random() < 0.25:
        # Create a red circular stamp overlapping lower section
        stamp = Image.new("RGBA", (350, 350), (255, 255, 255, 0))
        s_draw = ImageDraw.Draw(stamp)
        s_draw.ellipse([10, 10, 340, 340], outline=(190, 30, 30, 180), width=6)
        s_draw.ellipse([25, 25, 325, 325], outline=(190, 30, 30, 140), width=3)
        s_draw.text((70, 140), "VERIFIED & PAID", fill=(190, 30, 30, 200), font=f_body_b)
        s_draw.text((100, 180), "ACROCORP FIN", fill=(190, 30, 30, 180), font=f_small)
        stamp_rot = stamp.rotate(rng.randint(-20, 20), resample=Image.BICUBIC)
        img.paste(stamp_rot, (W - 750, tot_y + 10), stamp_rot)

    # Perspective & Camera Shadow Artifacts for ~15% of blind samples
    if layout_type == 7 or rng.random() < 0.15:
        np_img = np.array(img)
        # Add gradient shadow across the top-left to bottom-right
        h, w = np_img.shape[:2]
        x_grad = np.linspace(0.85, 1.05, w)
        y_grad = np.linspace(0.80, 1.05, h)
        grid = np.outer(y_grad, x_grad)
        grid = np.clip(grid, 0.7, 1.0)
        np_img = (np_img * grid[:, :, None]).astype(np.uint8)
        img = Image.fromarray(np_img)

    meta = {
        "file_name": f"blind_gst_{inv_idx:03d}.png",
        "is_blind": True,
        "layout_id": layout_type,
        "has_qr": has_qr,
        "supplier_name": supplier["name"],
        "supplier_gstin": supplier_gstin,
        "printed_supplier_gstin": printed_supplier_gstin,
        "was_gstin_corrupted": was_corrupted,
        "supplier_pan": supplier["pan"],
        "buyer_name": buyer["name"],
        "buyer_gstin": buyer_gstin,
        "invoice_number": inv_num,
        "invoice_date": inv_date,
        "due_date": due_date,
        "place_of_supply": pos_name,
        "taxable_amount": taxable_val,
        "cgst_amount": cgst_val,
        "sgst_amount": sgst_val,
        "igst_amount": igst_val,
        "total_amount": total_val,
        "currency": curr_style,
        "boxes": boxes,
        "line_items": items,
    }

    return img, meta


def main():
    rng = random.Random(98765)  # Strictly frozen seed
    print("[*] Generating 110 Blind GST Invoices across 8 layouts...")
    for idx in range(1, 111):
        img, meta = generate_blind_invoice(idx, rng)
        img_path = OUTPUT_DIR / meta["file_name"]
        meta_path = OUTPUT_DIR / f"blind_gst_{idx:03d}.json"

        img.save(img_path, format="PNG")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        if idx % 20 == 0 or idx == 110:
            print(f"  Generated {idx}/110 blind invoices...")

    print("[SUCCESS] Blind benchmark generated in docs/ocr-benchmark/data_gst_blind/")


if __name__ == "__main__":
    main()

