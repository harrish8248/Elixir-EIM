"""
Generate demo invoices for live demonstration:
- 3 clean GST invoices
- 1 rotated (90 deg)
- 1 blurred
- 1 without QR code
- 1 with deliberately wrong GSTIN checksum
- 1 EICAR test file
Stored in docs/demo-samples/gst/ and docs/demo-samples/
"""

import base64
import json
from pathlib import Path
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import qrcode

from apps.api.app.content.idp.gstin import compute_gstin_check_char, STATE_CODES

DEMO_DIR = Path("docs/demo-samples/gst")
DEMO_DIR.mkdir(parents=True, exist_ok=True)

INDIAN_SUPPLIERS = [
    {"name": "Tata Consultancy Services Ltd", "pan": "AAACT2718E", "state": "27", "city": "Mumbai", "addr": "TCS House, Raveline Street, Fort"},
    {"name": "Infosys Technologies Pvt Ltd", "pan": "AABCI1234F", "state": "29", "city": "Bengaluru", "addr": "Electronics City, Hosur Road"},
    {"name": "CloudScale Networks India Pvt Ltd", "pan": "AAPFU0939F", "state": "27", "city": "Pune", "addr": "Cybercity Magarpatta, Hadapsar"},
    {"name": "Bharti Airtel Enterprise Services", "pan": "AAACB0123L", "state": "07", "city": "New Delhi", "addr": "Airtel Centre, Plot 16, Udyog Vihar"},
]

INDIAN_BUYERS = [
    {"name": "AcroCorp India Private Limited", "pan": "AABCA9876M", "state": "27", "city": "Mumbai", "addr": "One BKC, G Block, Bandra Kurla Complex"},
    {"name": "Bharat Digital Commerce Ltd", "pan": "AAACB4321Q", "state": "36", "city": "Hyderabad", "addr": "HITEC City, Madhapur"},
    {"name": "Apex Global Services India Ltd", "pan": "AABCA5432N", "state": "29", "city": "Bengaluru", "addr": "Prestige Tech Park, Marathahalli"},
]

BANKS = [
    {"name": "HDFC Bank Ltd", "ifsc": "HDFC0000123", "branch": "Fort Mumbai"},
    {"name": "State Bank of India", "ifsc": "SBIN0001234", "branch": "Industrial Finance"},
    {"name": "ICICI Bank Limited", "ifsc": "ICIC0000456", "branch": "BKC Mumbai"},
]

HSN_CATALOG = [
    {"hsn": "998313", "desc": "Information Technology (IT) Consulting Services", "rate": 18.0},
    {"hsn": "998314", "desc": "Cloud Infrastructure & Data Hosting Bandwidth", "rate": 18.0},
    {"hsn": "998315", "desc": "Enterprise Software Licensing & Annual Support", "rate": 18.0},
    {"hsn": "847130", "desc": "Server Rack Infrastructure Hardware Units", "rate": 18.0},
]


def make_valid_gstin(pan: str, state: str, entity_code: str = "1") -> str:
    first14 = f"{state}{pan}{entity_code}Z"
    check = compute_gstin_check_char(first14)
    return f"{first14}{check}"


def render_invoice_image(
    doc_id: str,
    supplier: dict,
    buyer: dict,
    inv_no: str,
    inv_date: str,
    po_no: str,
    include_qr: bool = True,
    corrupt_checksum: bool = False,
    degradation: str = "clean",
) -> tuple[Path, dict]:
    page_w, page_h = 2550, 3300
    img = Image.new("RGB", (page_w, page_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arialbd.ttf", 52)
        font_h1 = ImageFont.truetype("arialbd.ttf", 38)
        font_h2 = ImageFont.truetype("arialbd.ttf", 32)
        font_bold = ImageFont.truetype("arialbd.ttf", 28)
        font_reg = ImageFont.truetype("arial.ttf", 26)
        font_small = ImageFont.truetype("arial.ttf", 22)
    except IOError:
        font_title = font_h1 = font_h2 = font_bold = font_reg = font_small = ImageFont.load_default()

    # Outer border
    draw.rectangle([(60, 60), (page_w - 60, page_h - 60)], outline=(30, 41, 59), width=4)

    # Tax calculation
    is_inter_state = supplier["state"] != buyer["state"]
    subtotal = 100000.0
    if is_inter_state:
        cgst_val = 0.0
        sgst_val = 0.0
        igst_val = round(subtotal * 0.18, 2)
    else:
        cgst_val = round(subtotal * 0.09, 2)
        sgst_val = round(subtotal * 0.09, 2)
        igst_val = 0.0
    total_val = round(subtotal + cgst_val + sgst_val + igst_val, 2)

    supplier_gstin = make_valid_gstin(supplier["pan"], supplier["state"])
    if corrupt_checksum:
        # Deliberately corrupt check char
        last_char = supplier_gstin[-1]
        corrupted_char = "X" if last_char != "X" else "Y"
        supplier_gstin = supplier_gstin[:-1] + corrupted_char

    buyer_gstin = make_valid_gstin(buyer["pan"], buyer["state"])

    # Header Title
    draw.text((120, 100), "TAX INVOICE", fill=(15, 23, 42), font=font_title)
    draw.text((120, 170), "(Issued under Section 31 of CGST Act, 2017)", fill=(71, 85, 105), font=font_small)

    # e-Invoice QR Code
    if include_qr:
        qr_payload = {
            "SellerGstin": supplier_gstin,
            "BuyerGstin": buyer_gstin,
            "DocNo": inv_no,
            "DocTyp": "INV",
            "DocDate": inv_date,
            "TotInvVal": total_val,
            "ItemCnt": 1,
            "MainHsnCode": "998313",
            "Irn": f"demo-irn-{doc_id}-9a8b7c6d5e4f3a2b1",
        }
        encoded_jwt = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9." + base64.urlsafe_b64encode(
            json.dumps(qr_payload).encode("utf-8")
        ).decode("utf-8").rstrip("=") + ".offline_signature"

        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=4,
        )
        qr.add_data(encoded_jwt)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        img.paste(qr_img, (page_w - 450, 90))

    # Supplier Details
    draw.rectangle([(100, 230), (page_w - 100, 520)], outline=(148, 163, 184), width=2)
    draw.rectangle([(100, 230), (page_w - 100, 280)], fill=(241, 245, 249))
    draw.text((120, 242), "SUPPLIER / ISSUER DETAILS", fill=(30, 41, 59), font=font_h2)

    draw.text((120, 300), supplier["name"], fill=(15, 23, 42), font=font_bold)
    draw.text((120, 345), f"Address: {supplier['addr']}, {supplier['city']}, {STATE_CODES.get(supplier['state'])}", fill=(51, 65, 85), font=font_reg)
    draw.text((120, 390), f"PAN: {supplier['pan']}    State Code: {supplier['state']}", fill=(51, 65, 85), font=font_reg)
    draw.text((120, 435), f"Supplier GSTIN: {supplier_gstin}", fill=(15, 23, 42), font=font_bold)

    # Buyer Details
    draw.rectangle([(100, 540), (page_w - 100, 830)], outline=(148, 163, 184), width=2)
    draw.rectangle([(100, 540), (page_w - 100, 590)], fill=(241, 245, 249))
    draw.text((120, 552), "BUYER / RECIPIENT DETAILS (BILLED TO)", fill=(30, 41, 59), font=font_h2)

    draw.text((120, 610), buyer["name"], fill=(15, 23, 42), font=font_bold)
    draw.text((120, 655), f"Address: {buyer['addr']}, {buyer['city']}, {STATE_CODES.get(buyer['state'])}", fill=(51, 65, 85), font=font_reg)
    draw.text((120, 700), f"PAN: {buyer['pan']}    State Code: {buyer['state']}", fill=(51, 65, 85), font=font_reg)
    draw.text((120, 745), f"Buyer GSTIN: {buyer_gstin}", fill=(15, 23, 42), font=font_bold)

    # Invoice Metadata Bar
    draw.rectangle([(100, 850), (page_w - 100, 970)], outline=(148, 163, 184), width=2, fill=(248, 250, 252))
    draw.text((120, 870), f"Invoice Number: {inv_no}", fill=(15, 23, 42), font=font_bold)
    draw.text((800, 870), f"Invoice Date: {inv_date}", fill=(15, 23, 42), font=font_bold)
    draw.text((1400, 870), f"PO Number: {po_no}", fill=(15, 23, 42), font=font_bold)
    draw.text((120, 920), f"Place of Supply: {STATE_CODES.get(buyer['state'])} ({buyer['state']})", fill=(30, 41, 59), font=font_reg)
    draw.text((800, 920), "Supply Type: B2B Regular", fill=(30, 41, 59), font=font_reg)

    # Line Item Table
    table_top = 1010
    draw.rectangle([(100, table_top), (page_w - 100, table_top + 60)], fill=(30, 41, 59))
    draw.text((120, table_top + 14), "S.No", fill=(255, 255, 255), font=font_bold)
    draw.text((240, table_top + 14), "Description of Goods / Services", fill=(255, 255, 255), font=font_bold)
    draw.text((1250, table_top + 14), "HSN/SAC", fill=(255, 255, 255), font=font_bold)
    draw.text((1500, table_top + 14), "Qty", fill=(255, 255, 255), font=font_bold)
    draw.text((1700, table_top + 14), "Unit Rate", fill=(255, 255, 255), font=font_bold)
    draw.text((2050, table_top + 14), "Taxable Amount", fill=(255, 255, 255), font=font_bold)

    # Row 1
    row_y = table_top + 70
    draw.text((140, row_y + 10), "1", fill=(15, 23, 42), font=font_reg)
    draw.text((240, row_y + 10), HSN_CATALOG[0]["desc"], fill=(15, 23, 42), font=font_reg)
    draw.text((1250, row_y + 10), HSN_CATALOG[0]["hsn"], fill=(15, 23, 42), font=font_bold)
    draw.text((1520, row_y + 10), "1.00", fill=(15, 23, 42), font=font_reg)
    draw.text((1700, row_y + 10), f"INR {subtotal:,.2f}", fill=(15, 23, 42), font=font_reg)
    draw.text((2050, row_y + 10), f"INR {subtotal:,.2f}", fill=(15, 23, 42), font=font_bold)

    draw.line([(100, row_y + 50), (page_w - 100, row_y + 50)], fill=(203, 213, 225), width=1)

    # Tax Summary Box
    tax_y = 1500
    draw.rectangle([(page_w - 950, tax_y), (page_w - 100, tax_y + 360)], outline=(148, 163, 184), width=2, fill=(248, 250, 252))
    draw.text((page_w - 920, tax_y + 20), f"Taxable Value: INR {subtotal:,.2f}", fill=(15, 23, 42), font=font_bold)
    draw.text((page_w - 920, tax_y + 70), f"CGST Amount: INR {cgst_val:,.2f}", fill=(51, 65, 85), font=font_reg)
    draw.text((page_w - 920, tax_y + 120), f"SGST Amount: INR {sgst_val:,.2f}", fill=(51, 65, 85), font=font_reg)
    draw.text((page_w - 920, tax_y + 170), f"IGST Amount: INR {igst_val:,.2f}", fill=(51, 65, 85), font=font_reg)
    draw.line([(page_w - 930, tax_y + 230), (page_w - 120, tax_y + 230)], fill=(203, 213, 225), width=2)
    draw.text((page_w - 920, tax_y + 260), f"Total Invoice Amount: INR {total_val:,.2f}", fill=(15, 23, 42), font=font_title)

    # Bank Details Box
    bank = BANKS[0]
    draw.rectangle([(100, tax_y), (page_w - 1000, tax_y + 360)], outline=(148, 163, 184), width=2, fill=(241, 245, 249))
    draw.text((120, tax_y + 20), "BANK ACCOUNT DETAILS (FOR NEFT / RTGS)", fill=(30, 41, 59), font=font_h2)
    draw.text((120, tax_y + 70), f"Bank Name: {bank['name']}", fill=(51, 65, 85), font=font_reg)
    draw.text((120, tax_y + 120), "Account Number: 50200012345678", fill=(15, 23, 42), font=font_bold)
    draw.text((120, tax_y + 170), f"Bank IFSC Code: {bank['ifsc']}", fill=(15, 23, 42), font=font_bold)
    draw.text((120, tax_y + 220), f"Branch: {bank['branch']}", fill=(51, 65, 85), font=font_reg)
    draw.text((120, tax_y + 280), "Terms: Payment due within 30 days. E.&O.E.", fill=(100, 116, 139), font=font_small)

    # Degradation options
    if degradation == "rotated":
        img = img.rotate(90, expand=True)
    elif degradation == "blurred":
        img = img.filter(ImageFilter.GaussianBlur(radius=1.8))

    output_path = DEMO_DIR / f"{doc_id}.png"
    img.save(str(output_path), "PNG")

    meta = {
        "doc_id": doc_id,
        "supplier_gstin": supplier_gstin,
        "buyer_gstin": buyer_gstin,
        "invoice_number": inv_no,
        "invoice_date": inv_date,
        "po_number": po_no,
        "taxable_value": subtotal,
        "cgst": cgst_val,
        "sgst": sgst_val,
        "igst": igst_val,
        "total_amount": total_val,
        "is_valid_checksum": not corrupt_checksum,
        "has_qr": include_qr,
        "degradation": degradation,
    }
    return output_path, meta


def main():
    print("Generating demo samples for live demonstration...")

    # 1. 3 Clean invoices
    p1, m1 = render_invoice_image(
        "demo_gst_01_clean",
        INDIAN_SUPPLIERS[0], INDIAN_BUYERS[0],
        "INV-2026-DEMO-001", "2026-10-25", "PO-2026-901",
        include_qr=True, corrupt_checksum=False, degradation="clean"
    )
    print(f"Generated: {p1.name}")

    p2, m2 = render_invoice_image(
        "demo_gst_02_clean",
        INDIAN_SUPPLIERS[1], INDIAN_BUYERS[0],
        "INV-2026-DEMO-002", "2026-10-26", "PO-2026-902",
        include_qr=True, corrupt_checksum=False, degradation="clean"
    )
    print(f"Generated: {p2.name}")

    p3, m3 = render_invoice_image(
        "demo_gst_03_clean",
        INDIAN_SUPPLIERS[2], INDIAN_BUYERS[1],
        "INV-2026-DEMO-003", "2026-10-27", "PO-2026-903",
        include_qr=True, corrupt_checksum=False, degradation="clean"
    )
    print(f"Generated: {p3.name}")

    # 2. 1 Rotated invoice
    p4, m4 = render_invoice_image(
        "demo_gst_04_rotated",
        INDIAN_SUPPLIERS[3], INDIAN_BUYERS[0],
        "INV-2026-DEMO-004", "2026-10-28", "PO-2026-904",
        include_qr=True, corrupt_checksum=False, degradation="rotated"
    )
    print(f"Generated: {p4.name}")

    # 3. 1 Blurred invoice
    p5, m5 = render_invoice_image(
        "demo_gst_05_blurred",
        INDIAN_SUPPLIERS[0], INDIAN_BUYERS[2],
        "INV-2026-DEMO-005", "2026-10-29", "PO-2026-905",
        include_qr=True, corrupt_checksum=False, degradation="blurred"
    )
    print(f"Generated: {p5.name}")

    # 4. 1 Invoice without QR code
    p6, m6 = render_invoice_image(
        "demo_gst_06_no_qr",
        INDIAN_SUPPLIERS[2], INDIAN_BUYERS[0],
        "INV-2026-DEMO-006", "2026-10-29", "PO-2026-906",
        include_qr=False, corrupt_checksum=False, degradation="clean"
    )
    print(f"Generated: {p6.name}")

    # 5. 1 Invoice with deliberately wrong GSTIN checksum
    p7, m7 = render_invoice_image(
        "demo_gst_07_invalid_gstin",
        INDIAN_SUPPLIERS[2], INDIAN_BUYERS[0],
        "INV-2026-DEMO-007", "2026-10-29", "PO-2026-907",
        include_qr=True, corrupt_checksum=True, degradation="clean"
    )
    print(f"Generated: {p7.name} (Deliberately corrupted checksum: {m7['supplier_gstin']})")

    # 6. Safe EICAR test string
    eicar_dir = Path("docs/demo-samples")
    eicar_path = eicar_dir / "eicar_test.txt"
    eicar_content = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    eicar_path.write_text(eicar_content, encoding="utf-8")
    print(f"Generated safe EICAR test file: {eicar_path} ({len(eicar_content)} bytes)")


if __name__ == "__main__":
    main()

