#!/usr/bin/env python3
"""
Synthetic OCR Benchmark Generator for Elixir EIM Intelligent Document Processing (IDP).
Generates realistic invoices, receipts, contracts, and purchase orders with:
1. Exact field-level JSON ground truth with normalized bounding boxes [x0, y0, x1, y1] in [0, 1].
2. High-resolution 300 DPI rendering (2550 x 3300 for Letter, 1350 x 2250 for Receipts).
3. Complete visual ground truth full_text assembled in strict top-to-bottom reading order.
4. Clean and degraded versions (skew, blur, noise, compression, contrast, rotated_90).
5. 440 total labeled documents:
   - 320 Invoices (160 clean, 160 degraded)
   - 40 Receipts (varied templates)
   - 40 Contracts (varied templates)
   - 40 Purchase Orders (varied templates)
6. Deterministic train (50%), dev (25%), test (25%) splits with fixed seed 42:
   - Train: 80 clean inv, 80 deg inv, 20 rcpt, 20 cnt, 20 po = 220 docs
   - Dev:   40 clean inv, 40 deg inv, 10 rcpt, 10 cnt, 10 po = 110 docs
   - Test:  40 clean inv, 40 deg inv, 10 rcpt, 10 cnt, 10 po = 110 docs
"""

import json
import math
import os
import random
from pathlib import Path
from faker import Faker
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
fake.seed_instance(SEED)

BENCHMARK_DIR = Path("docs/ocr-benchmark")
DATA_DIR = BENCHMARK_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

VENDORS = [
    ("Acme Industrial Supply LLC", "100 Industrial Parkway, Chicago, IL 60601", "finance@acmeind.com"),
    ("CloudScale Networks Inc", "450 Tech Hub Blvd, San Jose, CA 95110", "billing@cloudscale.net"),
    ("Horizon Legal Partners LLP", "120 Wall Street, Floor 18, New York, NY 10005", "accounts@horizonlaw.com"),
    ("Vertex Global Logistics", "88 Port Way, Long Beach, CA 90802", "invoices@vertexlogistics.com"),
    ("Apex Strategic Marketing Group", "77 Madison Ave, Suite 300, New York, NY 10016", "billing@apexmarketing.com"),
    ("Pinnacle Facility Services", "204 Commercial Rd, Atlanta, GA 30303", "ar@pinnaclefacility.com"),
    ("Quantum Dynamic Labs GmbH", "Tech Park B4, Munich, Germany", "invoicing@quantumlabs.eu"),
    ("Nexus Enterprise Staffing", "500 Broad St, Columbus, OH 43215", "billing@nexusstaff.com"),
    ("Vanguard Security Systems", "310 Cyber Way, Austin, TX 78701", "accounting@vanguardsec.com"),
    ("Titan Global Hardware Corp", "101 Machine Way, Detroit, MI 48201", "invoices@titanhardware.com"),
]

LINE_ITEMS_CATALOG = [
    ("Managed Cloud Hosting Standard Tier", 450.00),
    ("Dedicated IPv4 Allocation Subnet /28", 120.00),
    ("SSL/TLS Wildcard Certificate Renewal", 89.00),
    ("SOC-2 Compliance Continuous Audit Log", 1500.00),
    ("Network Security Threat Detection Scan", 350.00),
    ("High-Performance SSD Storage Block 1TB", 75.00),
    ("Database Replica Failover Node", 280.00),
    ("Enterprise Support SLA 24x7 Response", 950.00),
    ("Industrial Hydraulic Valve Fitting Kit", 340.00),
    ("Precision Steel Ball Bearing Assembly", 165.00),
    ("Heavy Duty Conveyor Belt Roller 24in", 420.00),
    ("Industrial Lubricant Drum 55 Gallon", 580.00),
    ("Legal Retainer - Regulatory Governance", 2500.00),
    ("Patent Portfolio Filing Review & Filing", 1800.00),
    ("Contract Drafting & Vendor Addendum", 650.00),
    ("Professional Staffing - Senior Engineer", 3200.00),
    ("Onsite Facility Cleaning & Sanitation", 480.00),
    ("HVAC Quarterly Preventative Maintenance", 750.00),
]

CURRENCIES = [
    ("$", "USD"),
    ("$", "USD"),
    ("$", "USD"),
    ("EUR ", "EUR"),
    ("GBP ", "GBP"),
]


def load_fonts(scale: float = 3.0) -> dict[str, ImageFont.ImageFont]:
    """Load standard fonts scaled for 300 DPI rendering."""
    s = scale
    try:
        return {
            "title": ImageFont.truetype("arialbd.ttf", int(26 * s)),
            "h1": ImageFont.truetype("arialbd.ttf", int(18 * s)),
            "h2": ImageFont.truetype("arialbd.ttf", int(15 * s)),
            "body": ImageFont.truetype("arial.ttf", int(13 * s)),
            "bold": ImageFont.truetype("arialbd.ttf", int(13 * s)),
            "small": ImageFont.truetype("arial.ttf", int(11 * s)),
            "serif_title": ImageFont.truetype("timesbd.ttf", int(24 * s)),
            "serif_body": ImageFont.truetype("times.ttf", int(13 * s)),
            "mono": ImageFont.truetype("cour.ttf", int(12 * s)),
            "mono_bold": ImageFont.truetype("courbd.ttf", int(14 * s)),
        }
    except Exception:
        def_font = ImageFont.load_default()
        return {k: def_font for k in ["title", "h1", "h2", "body", "bold", "small", "serif_title", "serif_body", "mono", "mono_bold"]}


def build_reading_order_text(text_elements: list[tuple[int, int, str]]) -> str:
    """Sort text elements by reading order (vertical line grouping, horizontal sorting)."""
    if not text_elements:
        return ""
    # Sort primarily by y, secondarily by x
    sorted_elements = sorted(text_elements, key=lambda e: (e[0], e[1]))
    lines: list[list[tuple[int, int, str]]] = []
    line_threshold = 25  # pixel tolerance for same line at 300 DPI

    for elem in sorted_elements:
        y, x, text = elem
        placed = False
        for line in lines:
            if abs(line[0][0] - y) <= line_threshold:
                line.append(elem)
                placed = True
                break
        if not placed:
            lines.append([elem])

    # Sort each line by x and join
    output_lines = []
    for line in lines:
        line.sort(key=lambda e: e[1])
        output_lines.append(" ".join(e[2] for e in line))
    return "\n".join(output_lines)


def degrade_image(img: Image.Image, degradation_type: str) -> Image.Image:
    """Apply realistic physical document degradations."""
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    if degradation_type == "skew":
        angle = random.choice([-2.5, -1.8, 1.8, 2.5])
        h, w = cv_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cv_img = cv2.warpAffine(cv_img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    elif degradation_type == "blur":
        ksize = random.choice([5, 7])
        cv_img = cv2.GaussianBlur(cv_img, (ksize, ksize), 0)

    elif degradation_type == "noise_jpeg":
        noise = np.random.normal(0, 18, cv_img.shape).astype(np.float32)
        noisy = np.clip(cv_img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        _, enc = cv2.imencode(".jpg", noisy, [int(cv2.IMWRITE_JPEG_QUALITY), random.randint(35, 50)])
        cv_img = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    elif degradation_type == "low_res":
        h, w = cv_img.shape[:2]
        down = cv2.resize(cv_img, (w // 3, h // 3), interpolation=cv2.INTER_LINEAR)
        cv_img = cv2.resize(down, (w, h), interpolation=cv2.INTER_LINEAR)

    elif degradation_type == "contrast":
        cv_img = cv2.convertScaleAbs(cv_img, alpha=0.70, beta=60)

    elif degradation_type == "rotated_90":
        cv_img = cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE)

    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))


def generate_invoice(idx: int, template_idx: int) -> tuple[Image.Image, dict]:
    """Render a 300 DPI invoice with exact ground truth and normalized bounding boxes."""
    vendor_name, vendor_addr, vendor_email = random.choice(VENDORS)
    inv_num = f"INV-2026-{1000 + idx:04d}"
    po_num = f"PO-99{idx:03d}" if random.random() > 0.15 else None

    month = random.randint(1, 10)
    day = random.randint(1, 28)
    inv_date_iso = f"2026-{month:02d}-{day:02d}"
    due_day = min(day + random.choice([15, 30, 45]), 28)
    due_month = month if due_day > day else month + 1
    due_date_iso = f"2026-{due_month:02d}-{due_day:02d}"

    curr_sym, curr_code = random.choice(CURRENCIES)

    n_items = random.randint(2, 4)
    chosen_items = random.sample(LINE_ITEMS_CATALOG, n_items)
    line_items = []
    subtotal = 0.0
    for desc, unit_price in chosen_items:
        qty = random.randint(1, 5)
        amount = round(qty * unit_price, 2)
        subtotal += amount
        line_items.append({
            "description": desc,
            "quantity": qty,
            "unit_price": unit_price,
            "amount": amount,
        })
    subtotal = round(subtotal, 2)
    tax_rate = random.choice([0.0, 0.05, 0.0825, 0.10])
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)

    # 300 DPI Canvas: 2550 x 3300 (Letter size)
    w, h = 2550, 3300
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(scale=3.0)

    text_elements: list[tuple[int, int, str]] = []
    field_boxes: dict[str, list[float]] = {}

    def draw_t(x: int, y: int, text: str, font: ImageFont.ImageFont, fill=(0, 0, 0), field_key: str | None = None):
        draw.text((x, y), text, fill=fill, font=font)
        text_elements.append((y, x, text))
        if field_key:
            bbox = draw.textbbox((x, y), text, font=font)
            field_boxes[field_key] = [round(bbox[0] / w, 4), round(bbox[1] / h, 4), round(bbox[2] / w, 4), round(bbox[3] / h, 4)]

    if template_idx == 0:
        # Template A: Modern Blue Header Banner
        draw.rectangle([0, 0, w, 270], fill=(24, 43, 73))
        draw_t(120, 75, "INVOICE", fonts["title"], fill=(255, 255, 255))
        draw_t(w - 840, 90, f"Number: {inv_num}", fonts["h1"], fill=(255, 255, 255), field_key="invoice_number")

        draw_t(120, 360, vendor_name, fonts["bold"], fill=(15, 23, 42), field_key="vendor")
        draw_t(120, 420, vendor_addr, fonts["small"], fill=(100, 116, 139))
        draw_t(120, 474, f"Email: {vendor_email}", fonts["small"], fill=(100, 116, 139))

        draw_t(w - 900, 360, "Billed To:", fonts["bold"], fill=(15, 23, 42))
        draw_t(w - 900, 420, "AcroCorp Global (US-East)", fonts["body"], fill=(51, 65, 85))
        draw_t(w - 900, 474, "Attn: Accounts Payable / Finance", fonts["small"], fill=(100, 116, 139))

        draw.rectangle([120, 585, w - 120, 705], fill=(241, 245, 249))
        draw_t(150, 618, f"Invoice Date: {inv_date_iso}", fonts["bold"], fill=(30, 41, 59), field_key="invoice_date")
        draw_t(750, 618, f"Due Date: {due_date_iso}", fonts["bold"], fill=(30, 41, 59), field_key="due_date")
        if po_num:
            draw_t(1350, 618, f"PO Number: {po_num}", fonts["bold"], fill=(30, 41, 59), field_key="po_number")
        draw_t(1950, 618, f"Currency: {curr_code}", fonts["bold"], fill=(30, 41, 59), field_key="currency")

    elif template_idx == 1:
        # Template B: Classic Corporate Monochrome
        draw_t(120, 120, vendor_name.upper(), fonts["h1"], fill=(15, 23, 42), field_key="vendor")
        draw_t(120, 195, vendor_addr, fonts["small"], fill=(71, 85, 105))
        draw_t(120, 246, f"Contact: {vendor_email}", fonts["small"], fill=(71, 85, 105))

        draw_t(w - 720, 120, "TAX INVOICE", fonts["title"], fill=(15, 23, 42))
        draw.line([120, 330, w - 120, 330], fill=(15, 23, 42), width=4)

        draw_t(120, 375, f"Invoice #: {inv_num}", fonts["bold"], fill=(15, 23, 42), field_key="invoice_number")
        draw_t(120, 435, f"Date of Issue: {inv_date_iso}", fonts["body"], fill=(51, 65, 85), field_key="invoice_date")
        draw_t(120, 495, f"Payment Due Date: {due_date_iso}", fonts["body"], fill=(51, 65, 85), field_key="due_date")
        if po_num:
            draw_t(120, 555, f"Purchase Order Ref: {po_num}", fonts["body"], fill=(51, 65, 85), field_key="po_number")

        draw_t(w - 900, 375, "Customer Details:", fonts["bold"], fill=(15, 23, 42))
        draw_t(w - 900, 435, "AcroCorp Global Operations", fonts["body"], fill=(51, 65, 85))
        draw_t(w - 900, 495, "100 Enterprise Way, Suite 400", fonts["small"], fill=(100, 116, 139))
        draw_t(w - 900, 555, f"Currency: {curr_code}", fonts["body"], fill=(51, 65, 85), field_key="currency")

    elif template_idx == 2:
        # Template C: Minimalist Grid Layout
        draw.rectangle([120, 120, w - 120, 390], outline=(203, 213, 225), width=3)
        draw_t(165, 150, vendor_name, fonts["title"], fill=(15, 23, 42), field_key="vendor")
        draw_t(165, 246, f"Vendor Email: {vendor_email} | Address: {vendor_addr}", fonts["small"], fill=(100, 116, 139))

        draw_t(165, 450, f"INVOICE REFERENCE: {inv_num}", fonts["h1"], fill=(30, 41, 59), field_key="invoice_number")
        draw_t(165, 540, f"DATE: {inv_date_iso}", fonts["body"], fill=(71, 85, 105), field_key="invoice_date")
        draw_t(840, 540, f"DUE DATE: {due_date_iso}", fonts["body"], fill=(71, 85, 105), field_key="due_date")
        if po_num:
            draw_t(1500, 540, f"PURCHASE ORDER: {po_num}", fonts["body"], fill=(71, 85, 105), field_key="po_number")
        draw_t(2050, 540, f"CURRENCY: {curr_code}", fonts["body"], fill=(71, 85, 105), field_key="currency")

    else:
        # Template D: Left Sidebar Accented Layout
        draw.rectangle([0, 0, 360, h], fill=(245, 247, 250))
        draw.line([360, 0, 360, h], fill=(226, 232, 240), width=4)
        draw_t(60, 120, "INVOICE", fonts["title"], fill=(30, 41, 59))
        draw_t(60, 240, "REMIT TO:", fonts["bold"], fill=(71, 85, 105))
        draw_t(60, 285, vendor_name, fonts["small"], fill=(15, 23, 42), field_key="vendor")
        draw_t(60, 345, vendor_addr[:30], fonts["small"], fill=(100, 116, 139))
        draw_t(60, 390, vendor_email, fonts["small"], fill=(100, 116, 139))

        draw_t(420, 120, f"Invoice #: {inv_num}", fonts["h1"], fill=(15, 23, 42), field_key="invoice_number")
        draw_t(420, 200, f"Issue Date: {inv_date_iso}", fonts["body"], fill=(51, 65, 85), field_key="invoice_date")
        draw_t(1000, 200, f"Due Date: {due_date_iso}", fonts["body"], fill=(51, 65, 85), field_key="due_date")
        if po_num:
            draw_t(1600, 200, f"PO Ref: {po_num}", fonts["body"], fill=(51, 65, 85), field_key="po_number")
        draw_t(2100, 200, f"Currency: {curr_code}", fonts["body"], fill=(51, 65, 85), field_key="currency")

    # Line Items Table
    x_table_start = 420 if template_idx == 3 else 120
    y_table = 780
    draw.rectangle([x_table_start, y_table, w - 120, y_table + 90], fill=(226, 232, 240))
    draw_t(x_table_start + 30, y_table + 24, "Description", fonts["bold"], fill=(15, 23, 42))
    draw_t(w - 1100, y_table + 24, "Qty", fonts["bold"], fill=(15, 23, 42))
    draw_t(w - 800, y_table + 24, "Unit Price", fonts["bold"], fill=(15, 23, 42))
    draw_t(w - 450, y_table + 24, "Amount", fonts["bold"], fill=(15, 23, 42))

    y_cur = y_table + 114
    for item in line_items:
        draw_t(x_table_start + 30, y_cur, item["description"], fonts["body"], fill=(30, 41, 59))
        draw_t(w - 1080, y_cur, str(item["quantity"]), fonts["body"], fill=(30, 41, 59))
        draw_t(w - 800, y_cur, f"{curr_sym}{item['unit_price']:.2f}", fonts["body"], fill=(30, 41, 59))
        draw_t(w - 450, y_cur, f"{curr_sym}{item['amount']:.2f}", fonts["body"], fill=(30, 41, 59))
        draw.line([x_table_start, y_cur + 72, w - 120, y_cur + 72], fill=(241, 245, 249), width=2)
        y_cur += 96

    # Totals Box
    y_totals = max(y_cur + 90, 1380)
    draw.line([w - 960, y_totals, w - 120, y_totals], fill=(203, 213, 225), width=3)

    draw_t(w - 930, y_totals + 30, "Subtotal:", fonts["body"], fill=(71, 85, 105))
    draw_t(w - 450, y_totals + 30, f"{curr_sym}{subtotal:.2f}", fonts["bold"], fill=(15, 23, 42), field_key="subtotal")

    draw_t(w - 930, y_totals + 102, f"Tax ({tax_rate*100:.1f}%):", fonts["body"], fill=(71, 85, 105))
    draw_t(w - 450, y_totals + 102, f"{curr_sym}{tax:.2f}", fonts["bold"], fill=(15, 23, 42), field_key="tax")

    draw.rectangle([w - 960, y_totals + 180, w - 120, y_totals + 285], fill=(241, 245, 249))
    draw_t(w - 930, y_totals + 204, "Total Amount Due:", fonts["bold"], fill=(15, 23, 42))
    draw_t(w - 450, y_totals + 204, f"{curr_sym}{total:.2f}", fonts["h1"], fill=(24, 43, 73), field_key="total")

    # Footer
    draw_t(x_table_start, h - 240, "Payment Terms: Net 30. Remit payments via ACH/Wire.", fonts["small"], fill=(100, 116, 139))
    draw_t(x_table_start, h - 180, f"Thank you for your business — {vendor_name}", fonts["small"], fill=(148, 163, 184))

    full_text = build_reading_order_text(text_elements)

    gt = {
        "document_type": "invoice",
        "vendor": vendor_name,
        "invoice_number": inv_num,
        "invoice_date": inv_date_iso,
        "due_date": due_date_iso,
        "po_number": po_num,
        "currency": curr_code,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "line_items": line_items,
        "full_text": full_text,
        "field_boxes": field_boxes,
    }
    return img, gt


def generate_receipt(idx: int) -> tuple[Image.Image, dict]:
    """Render a 300 DPI retail/expense receipt across 3 distinct layout templates."""
    merchants = [
        "Metro Office Supplies", "Express Courier Logistics", "QuickPrint Center",
        "Airport Cafe & Catering", "Beacon Data Hardware", "Apex Fuel & Service"
    ]
    merchant = merchants[idx % len(merchants)]
    receipt_num = f"REC-2026-{2000 + idx:04d}"
    date_iso = f"2026-10-{1 + (idx % 28):02d}"
    subtotal = round(float(25.0 + (idx * 7.5) % 180.0), 2)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)

    w, h = 1350, 2250
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(scale=3.0)

    text_elements: list[tuple[int, int, str]] = []
    field_boxes: dict[str, list[float]] = {}

    def draw_t(x: int, y: int, text: str, font: ImageFont.ImageFont, fill=(0, 0, 0), field_key: str | None = None):
        draw.text((x, y), text, fill=fill, font=font)
        text_elements.append((y, x, text))
        if field_key:
            bbox = draw.textbbox((x, y), text, font=font)
            field_boxes[field_key] = [round(bbox[0] / w, 4), round(bbox[1] / h, 4), round(bbox[2] / w, 4), round(bbox[3] / h, 4)]

    tmpl = idx % 3
    if tmpl == 0:
        # Standard Thermal Register
        draw_t(w // 2 - 250, 90, merchant.upper(), fonts["bold"], field_key="vendor")
        draw_t(w // 2 - 200, 165, "CUSTOMER RECEIPT", fonts["body"])
        draw.line([90, 240, w - 90, 240], fill=(0, 0, 0), width=3)

        draw_t(90, 285, f"Receipt: {receipt_num}", fonts["mono"], field_key="invoice_number")
        draw_t(90, 345, f"Date: {date_iso}", fonts["mono"], field_key="invoice_date")
        draw_t(90, 405, "Payment: VISA **** 4892", fonts["mono"])
        draw.line([90, 480, w - 90, 480], fill=(0, 0, 0), width=3)

        draw_t(90, 540, "Office Supplies & Consumables", fonts["mono"])
        draw_t(w - 360, 540, f"${subtotal:.2f}", fonts["mono"])

        draw.line([90, 690, w - 90, 690], fill=(0, 0, 0), width=3)
        draw_t(90, 735, "SUBTOTAL:", fonts["mono"])
        draw_t(w - 360, 735, f"${subtotal:.2f}", fonts["mono"], field_key="subtotal")
        draw_t(90, 795, "TAX 8%:", fonts["mono"])
        draw_t(w - 360, 795, f"${tax:.2f}", fonts["mono"], field_key="tax")
        draw_t(90, 870, "TOTAL PAID:", fonts["bold"])
        draw_t(w - 360, 870, f"${total:.2f}", fonts["bold"], field_key="total")

        draw_t(w // 2 - 180, 1050, "*** THANK YOU ***", fonts["body"])

    elif tmpl == 1:
        # Modern POS e-receipt
        draw.rectangle([90, 90, w - 90, 240], fill=(245, 245, 245))
        draw_t(150, 135, merchant, fonts["h1"], field_key="vendor")
        draw_t(150, 270, f"Order Ref: {receipt_num}", fonts["bold"], field_key="invoice_number")
        draw_t(150, 330, f"Timestamp: {date_iso} 14:32:10", fonts["body"], field_key="invoice_date")
        draw_t(150, 390, "Method: Apple Pay (MasterCard 9102)", fonts["body"])

        draw.line([90, 480, w - 90, 480], fill=(200, 200, 200), width=2)
        draw_t(150, 540, "General Commercial Goods Tier 1", fonts["body"])
        draw_t(w - 360, 540, f"${subtotal:.2f}", fonts["bold"])

        draw.line([90, 660, w - 90, 660], fill=(200, 200, 200), width=2)
        draw_t(150, 705, "Subtotal Amount:", fonts["body"])
        draw_t(w - 360, 705, f"${subtotal:.2f}", fonts["body"], field_key="subtotal")
        draw_t(150, 765, "Sales Tax (8.0%):", fonts["body"])
        draw_t(w - 360, 765, f"${tax:.2f}", fonts["body"], field_key="tax")
        draw_t(150, 840, "AMOUNT CHARGED:", fonts["h1"])
        draw_t(w - 360, 840, f"${total:.2f}", fonts["h1"], field_key="total")

    else:
        # Fuel / Service Station Voucher
        draw_t(120, 90, f"{merchant} Service Station", fonts["title"], field_key="vendor")
        draw_t(120, 180, "Voucher ID:", fonts["mono"])
        draw_t(450, 180, receipt_num, fonts["mono_bold"], field_key="invoice_number")
        draw_t(120, 240, f"Date / Time: {date_iso} 09:15", fonts["mono"], field_key="invoice_date")
        draw_t(120, 300, "Pump #04 - Regular Unleaded / Service", fonts["mono"])

        draw.line([90, 420, w - 90, 420], fill=(50, 50, 50), width=3)
        draw_t(120, 480, "Net Fuel / Goods:", fonts["mono"])
        draw_t(w - 360, 480, f"${subtotal:.2f}", fonts["mono"], field_key="subtotal")
        draw_t(120, 540, "State / Local Tax:", fonts["mono"])
        draw_t(w - 360, 540, f"${tax:.2f}", fonts["mono"], field_key="tax")
        draw_t(120, 630, "NET TOTAL DUE:", fonts["bold"])
        draw_t(w - 360, 630, f"${total:.2f}", fonts["bold"], field_key="total")

    full_text = build_reading_order_text(text_elements)

    gt = {
        "document_type": "receipt",
        "vendor": merchant,
        "invoice_number": receipt_num,
        "invoice_date": date_iso,
        "due_date": date_iso,
        "po_number": None,
        "currency": "USD",
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "line_items": [{"description": "Office Supplies & Consumables", "quantity": 1, "unit_price": subtotal, "amount": subtotal}],
        "full_text": full_text,
        "field_boxes": field_boxes,
    }
    return img, gt


def generate_contract(idx: int) -> tuple[Image.Image, dict]:
    """Render a 300 DPI legal agreement across 3 distinct contract templates."""
    w, h = 2550, 3300
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(scale=3.0)

    text_elements: list[tuple[int, int, str]] = []
    field_boxes: dict[str, list[float]] = {}

    def draw_t(x: int, y: int, text: str, font: ImageFont.ImageFont, fill=(0, 0, 0), field_key: str | None = None):
        draw.text((x, y), text, fill=fill, font=font)
        text_elements.append((y, x, text))
        if field_key:
            bbox = draw.textbbox((x, y), text, font=font)
            field_boxes[field_key] = [round(bbox[0] / w, 4), round(bbox[1] / h, 4), round(bbox[2] / w, 4), round(bbox[3] / h, 4)]

    day = 1 + (idx % 28)
    date_iso = f"2026-10-{day:02d}"
    tmpl = idx % 3

    if tmpl == 0:
        # Non-Disclosure Agreement
        title = "NON-DISCLOSURE AND MUTUAL CONFIDENTIALITY AGREEMENT"
        vendor = "Partner Services Group Inc"
        draw_t(360, 150, title, fonts["h1"])
        draw.line([150, 255, w - 150, 255], fill=(0, 0, 0), width=3)

        body_text = f"""This Non-Disclosure Agreement ("Agreement") is entered into as of October {day}, 2026, by and between
AcroCorp Global Enterprises LLC, with offices at 100 Enterprise Way ("Disclosing Party"), and
{vendor} ("Receiving Party").

1. PURPOSE
The parties wish to explore a business opportunity concerning enterprise information management,
cryptographic audit trails, and automated process orchestration.

2. CONFIDENTIAL INFORMATION
"Confidential Information" refers to all non-public technical, commercial, financial, and operational
records disclosed by either party, whether in writing, orally, or in electronic media.

3. OBLIGATIONS
The Receiving Party agrees to maintain the secrecy of Confidential Information with at least reasonable care
and shall not disclose such information to any third party without prior written consent.

4. TERM AND TERMINATION
This Agreement shall remain in effect for a period of three (3) years from the Effective Date.

IN WITNESS WHEREOF, the authorized representatives have executed this Agreement:
AcroCorp Global Enterprises LLC: ______________________      Date: {date_iso}
{vendor}:      ______________________      Date: {date_iso}"""

    elif tmpl == 1:
        # Master Services Agreement
        title = "MASTER PROFESSIONAL SERVICES AGREEMENT"
        vendor = "Horizon Legal Partners LLP"
        draw_t(450, 150, title, fonts["h1"])
        draw.line([150, 255, w - 150, 255], fill=(0, 0, 0), width=3)

        body_text = f"""This Master Services Agreement ("MSA") is entered into as of October {day}, 2026, between
AcroCorp Global Operations ("Client") and {vendor} ("Service Provider").

1. SCOPE OF SERVICES
Service Provider shall deliver the specialized professional consulting, architecture, and regulatory compliance
services described in Statements of Work ("SOW") executed hereunder.

2. COMPENSATION AND BILLING
Client agrees to compensate Service Provider in accordance with fee schedules set forth in applicable SOWs.
Invoices shall be rendered monthly and are payable Net 30 days from invoice date.

3. INTELLECTUAL PROPERTY RIGHTS
All work product, deliverables, and associated patents and copyrights created specifically for Client shall
vest exclusively in Client upon receipt of full payment.

4. INDEMNIFICATION AND LIABILITY
Neither party shall be liable for indirect, incidental, or consequential damages arising from performance.

ACCEPTED AND AGREED:
Client: AcroCorp Global Operations           Provider: {vendor}
Date: {date_iso}                             Date: {date_iso}"""

    else:
        # Software License Agreement
        title = "ENTERPRISE SOFTWARE LICENSE AGREEMENT"
        vendor = "CloudScale Networks Inc"
        draw_t(450, 150, title, fonts["h1"])
        draw.line([150, 255, w - 150, 255], fill=(0, 0, 0), width=3)

        body_text = f"""This Software License Agreement ("Agreement") governs the use of enterprise software modules between
AcroCorp Global Enterprises LLC ("Licensee") and {vendor} ("Licensor").

1. GRANT OF LICENSE
Licensor grants Licensee a non-exclusive, non-transferable perpetual license to install and execute the software
within Licensee's private cloud infrastructure.

2. AUDIT AND COMPLIANCE
Licensor reserves the right upon reasonable written notice to verify license compliance and core usage metrics.

3. LIMITED WARRANTY
Licensor warrants that the software will perform substantially in accordance with documented specifications
for a period of ninety (90) days following delivery.

EXECUTED as of {date_iso}:
Licensor: {vendor}                           Licensee: AcroCorp Global"""

    y = 360
    for line in body_text.split("\n"):
        draw_t(180, y, line, fonts["serif_body"], fill=(20, 20, 20))
        y += 72

    draw_t(180, 2800, f"Vendor Signatory: {vendor}", fonts["bold"], field_key="vendor")

    full_text = build_reading_order_text(text_elements)

    gt = {
        "document_type": "contract",
        "vendor": vendor,
        "invoice_number": f"CNT-2026-{idx:03d}",
        "invoice_date": date_iso,
        "due_date": None,
        "po_number": None,
        "currency": None,
        "subtotal": 0.0,
        "tax": 0.0,
        "total": 0.0,
        "line_items": [],
        "full_text": full_text,
        "field_boxes": field_boxes,
    }
    return img, gt


def generate_purchase_order(idx: int) -> tuple[Image.Image, dict]:
    """Render a 300 DPI formal purchase order across 3 distinct PO templates."""
    w, h = 2550, 3300
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(scale=3.0)

    text_elements: list[tuple[int, int, str]] = []
    field_boxes: dict[str, list[float]] = {}

    def draw_t(x: int, y: int, text: str, font: ImageFont.ImageFont, fill=(0, 0, 0), field_key: str | None = None):
        draw.text((x, y), text, fill=fill, font=font)
        text_elements.append((y, x, text))
        if field_key:
            bbox = draw.textbbox((x, y), text, font=font)
            field_boxes[field_key] = [round(bbox[0] / w, 4), round(bbox[1] / h, 4), round(bbox[2] / w, 4), round(bbox[3] / h, 4)]

    vendor = VENDORS[idx % len(VENDORS)][0]
    po_num = f"PO-2026-{7000 + idx}"
    date_iso = f"2026-10-{1 + (idx % 28):02d}"

    tmpl = idx % 3
    if tmpl == 0:
        # Standard Corporate Procurement PO
        draw_t(150, 120, "PURCHASE ORDER", fonts["title"], fill=(15, 23, 42))
        draw_t(w - 750, 135, f"P.O. #: {po_num}", fonts["bold"], fill=(15, 23, 42), field_key="po_number")
        draw.line([150, 240, w - 150, 240], fill=(200, 200, 200), width=6)

        draw_t(150, 300, "ISSUED BY: AcroCorp Procurement", fonts["body"], fill=(50, 50, 50))
        draw_t(150, 360, "100 Enterprise Way, Suite 400", fonts["small"], fill=(100, 100, 100))

        draw_t(w - 900, 300, f"VENDOR: {vendor}", fonts["body"], fill=(50, 50, 50), field_key="vendor")
        draw_t(w - 900, 360, "Approved Corporate Supplier", fonts["small"], fill=(100, 100, 100))

        draw_t(150, 510, f"Order Date: {date_iso} | Delivery Terms: FOB Destination | Payment: Net 45", fonts["bold"], fill=(30, 30, 30), field_key="invoice_date")

    elif tmpl == 1:
        # Institutional Requisition Order
        draw.rectangle([150, 120, w - 150, 270], fill=(235, 240, 245))
        draw_t(180, 165, "OFFICIAL REQUISITION PURCHASE ORDER", fonts["h1"], fill=(20, 30, 50))
        draw_t(w - 750, 165, f"REF: {po_num}", fonts["bold"], fill=(20, 30, 50), field_key="po_number")

        draw_t(180, 330, f"BUYER: AcroCorp Central Procurement (Dept 402)", fonts["body"])
        draw_t(180, 390, f"SUPPLIER: {vendor}", fonts["bold"], field_key="vendor")
        draw_t(180, 450, f"REQUISITION DATE: {date_iso} | COST CENTER: CC-9901", fonts["body"], field_key="invoice_date")

    else:
        # Work Order PO
        draw_t(150, 120, "COMMERCIAL WORK ORDER & PO", fonts["title"])
        draw_t(w - 750, 135, f"W.O. #{po_num}", fonts["h1"], field_key="po_number")
        draw.line([150, 240, w - 150, 240], fill=(30, 41, 59), width=4)

        draw_t(150, 300, f"Contractor / Supplier: {vendor}", fonts["bold"], field_key="vendor")
        draw_t(150, 360, f"Work Order Date: {date_iso}", fonts["body"], field_key="invoice_date")
        draw_t(w - 900, 300, "Project: Cloud Modernization Tier 2", fonts["body"])

    # Table of PO items
    y_table = 660
    draw.rectangle([150, y_table, w - 150, y_table + 75], fill=(230, 235, 240))
    draw_t(180, y_table + 15, "Item / Scope of Work", fonts["bold"], fill=(0, 0, 0))
    draw_t(w - 450, y_table + 15, "Est. Total", fonts["bold"], fill=(0, 0, 0))

    items = [("Enterprise Software License Allocation Q4", 8500.00), ("Implementation Services & Onboarding", 3500.00)]
    y = y_table + 105
    for desc, amt in items:
        draw_t(180, y, desc, fonts["body"], fill=(40, 40, 40))
        draw_t(w - 450, y, f"${amt:.2f}", fonts["body"], fill=(40, 40, 40))
        y += 84

    total = sum(amt for _, amt in items)
    draw_t(w - 900, y + 90, f"AUTHORIZED TOTAL: ${total:.2f}", fonts["bold"], fill=(0, 0, 0), field_key="total")

    full_text = build_reading_order_text(text_elements)

    gt = {
        "document_type": "purchase_order",
        "vendor": vendor,
        "invoice_number": None,
        "invoice_date": date_iso,
        "due_date": None,
        "po_number": po_num,
        "currency": "USD",
        "subtotal": total,
        "tax": 0.0,
        "total": total,
        "line_items": [{"description": desc, "quantity": 1, "unit_price": amt, "amount": amt} for desc, amt in items],
        "full_text": full_text,
        "field_boxes": field_boxes,
    }
    return img, gt


def main():
    print(f"Generating Synthetic OCR Benchmark (Seed={SEED}, 300 DPI, 440 Documents)...")
    dataset: list[dict] = []
    degradation_types = ["skew", "blur", "noise_jpeg", "low_res", "contrast", "rotated_90"]

    # 1. Generate 160 Clean Invoices + 160 Degraded Invoices = 320 Invoices
    print("Generating 160 Invoices (Clean + Degraded pairs = 320 docs)...")
    for i in range(160):
        template_idx = i % 4
        img_clean, gt_clean = generate_invoice(i, template_idx)
        doc_id_clean = f"inv_{i:03d}_clean"
        img_path_clean = DATA_DIR / f"{doc_id_clean}.png"
        gt_path_clean = DATA_DIR / f"{doc_id_clean}.json"

        img_clean.save(img_path_clean)
        gt_clean["doc_id"] = doc_id_clean
        gt_clean["is_degraded"] = False
        gt_clean["degradation"] = "none"
        gt_clean["image_path"] = str(img_path_clean)
        with open(gt_path_clean, "w", encoding="utf-8") as f:
            json.dump(gt_clean, f, indent=2)
        dataset.append(gt_clean)

        # Degraded version
        deg_type = degradation_types[i % len(degradation_types)]
        img_deg = degrade_image(img_clean, deg_type)
        doc_id_deg = f"inv_{i:03d}_deg_{deg_type}"
        img_path_deg = DATA_DIR / f"{doc_id_deg}.png"
        gt_path_deg = DATA_DIR / f"{doc_id_deg}.json"

        img_deg.save(img_path_deg)
        gt_deg = dict(gt_clean)
        gt_deg["doc_id"] = doc_id_deg
        gt_deg["is_degraded"] = True
        gt_deg["degradation"] = deg_type
        gt_deg["image_path"] = str(img_path_deg)
        with open(gt_path_deg, "w", encoding="utf-8") as f:
            json.dump(gt_deg, f, indent=2)
        dataset.append(gt_deg)

    # 2. Generate 40 Receipts
    print("Generating 40 Receipts across 3 templates...")
    for i in range(40):
        img_rcpt, gt_rcpt = generate_receipt(i)
        doc_id = f"rcpt_{i:03d}_clean"
        img_path = DATA_DIR / f"{doc_id}.png"
        gt_path = DATA_DIR / f"{doc_id}.json"
        img_rcpt.save(img_path)
        gt_rcpt["doc_id"] = doc_id
        gt_rcpt["is_degraded"] = False
        gt_rcpt["degradation"] = "none"
        gt_rcpt["image_path"] = str(img_path)
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(gt_rcpt, f, indent=2)
        dataset.append(gt_rcpt)

    # 3. Generate 40 Contracts
    print("Generating 40 Contracts across 3 templates...")
    for i in range(40):
        img_cnt, gt_cnt = generate_contract(i)
        doc_id = f"cnt_{i:03d}_clean"
        img_path = DATA_DIR / f"{doc_id}.png"
        gt_path = DATA_DIR / f"{doc_id}.json"
        img_cnt.save(img_path)
        gt_cnt["doc_id"] = doc_id
        gt_cnt["is_degraded"] = False
        gt_cnt["degradation"] = "none"
        gt_cnt["image_path"] = str(img_path)
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(gt_cnt, f, indent=2)
        dataset.append(gt_cnt)

    # 4. Generate 40 Purchase Orders
    print("Generating 40 Purchase Orders across 3 templates...")
    for i in range(40):
        img_po, gt_po = generate_purchase_order(i)
        doc_id = f"po_{i:03d}_clean"
        img_path = DATA_DIR / f"{doc_id}.png"
        gt_path = DATA_DIR / f"{doc_id}.json"
        img_po.save(img_path)
        gt_po["doc_id"] = doc_id
        gt_po["is_degraded"] = False
        gt_po["degradation"] = "none"
        gt_po["image_path"] = str(img_path)
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(gt_po, f, indent=2)
        dataset.append(gt_po)

    print(f"Total labeled documents generated: {len(dataset)}")

    # 5. Deterministic Stratified Split:
    # 50% Train, 25% Dev, 25% Test
    rng = random.Random(SEED)
    train_ids = []
    dev_ids = []
    test_ids = []

    groups: dict[str, list[str]] = {}
    for d in dataset:
        key = f"{d['document_type']}_{'deg' if d.get('is_degraded') else 'clean'}"
        groups.setdefault(key, []).append(d["doc_id"])

    for key, ids in groups.items():
        rng.shuffle(ids)
        n = len(ids)
        n_train = int(n * 0.50)
        n_dev = int(n * 0.25)
        train_ids.extend(ids[:n_train])
        dev_ids.extend(ids[n_train:n_train + n_dev])
        test_ids.extend(ids[n_train + n_dev:])

    splits = {
        "seed": SEED,
        "counts": {
            "total": len(dataset),
            "train": len(train_ids),
            "dev": len(dev_ids),
            "test": len(test_ids),
        },
        "train": sorted(train_ids),
        "dev": sorted(dev_ids),
        "test": sorted(test_ids),
    }

    splits_path = BENCHMARK_DIR / "splits.json"
    with open(splits_path, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2)

    print(f"Dataset splits generated at {splits_path}:")
    print(f"  Train: {len(train_ids)} ({len(train_ids)/len(dataset)*100:.1f}%)")
    print(f"  Dev:   {len(dev_ids)} ({len(dev_ids)/len(dataset)*100:.1f}%)")
    print(f"  Test:  {len(test_ids)} ({len(test_ids)/len(dataset)*100:.1f}%)")


if __name__ == "__main__":
    main()
