#!/usr/bin/env python3
"""
Synthetic OCR Benchmark Generator for Elixir EIM Intelligent Document Processing (IDP).
Generates realistic invoices, receipts, contracts, and purchase orders with:
1. Exact field-level JSON ground truth.
2. Clean (rendered at 300 DPI) and degraded versions (skew, blur, noise, compression, scan-artifacts).
3. Deterministic train (50%), dev (25%), test (25%) splits with fixed seed 42.
"""

import json
import os
import random
from pathlib import Path
from faker import Faker
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np

# Fixed seed for reproducibility
SEED = 42
random.seed(SEED)
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

def degrade_image(img: Image.Image, degradation_type: str) -> Image.Image:
    """Apply realistic physical document degradations."""
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    if degradation_type == "skew":
        # Slight rotation / skew (-4 to 4 degrees)
        angle = random.choice([-3.5, -2.0, 2.0, 3.5])
        h, w = cv_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cv_img = cv2.warpAffine(cv_img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    elif degradation_type == "blur":
        # Slight defocus / optical blur
        ksize = random.choice([3, 5])
        cv_img = cv2.GaussianBlur(cv_img, (ksize, ksize), 0)

    elif degradation_type == "noise_jpeg":
        # Gaussian noise + JPEG compression artifacts
        noise = np.random.normal(0, 15, cv_img.shape).astype(np.float32)
        noisy = np.clip(cv_img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        # Encode to JPEG with low quality and decode
        _, enc = cv2.imencode(".jpg", noisy, [int(cv2.IMWRITE_JPEG_QUALITY), random.randint(35, 55)])
        cv_img = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    elif degradation_type == "low_res":
        # Downsample and upsample (fax / low resolution copy)
        h, w = cv_img.shape[:2]
        down = cv2.resize(cv_img, (w // 2, h // 2), interpolation=cv2.INTER_LINEAR)
        cv_img = cv2.resize(down, (w, h), interpolation=cv2.INTER_LINEAR)

    elif degradation_type == "contrast":
        # Faded photocopy / low contrast
        cv_img = cv2.convertScaleAbs(cv_img, alpha=0.75, beta=50)

    elif degradation_type == "rotated_90":
        # 90 degrees rotation (testing OSD)
        cv_img = cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE)

    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

def generate_invoice(idx: int, template_idx: int) -> tuple[Image.Image, dict]:
    """Render a realistic invoice with ground truth metadata."""
    vendor_name, vendor_addr, vendor_email = random.choice(VENDORS)
    inv_num = f"INV-2026-{1000 + idx:04d}"
    po_num = f"PO-99{idx:03d}" if random.random() > 0.15 else None
    
    # Dates
    month = random.randint(1, 10)
    day = random.randint(1, 28)
    inv_date_iso = f"2026-{month:02d}-{day:02d}"
    due_day = min(day + random.choice([15, 30, 45]), 28)
    due_month = month if due_day > day else month + 1
    due_date_iso = f"2026-{due_month:02d}-{due_day:02d}"
    
    curr_sym, curr_code = random.choice(CURRENCIES)
    
    # Select 2 to 4 line items
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
            "amount": amount
        })
    subtotal = round(subtotal, 2)
    tax_rate = random.choice([0.0, 0.05, 0.0825, 0.10])
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    
    # Render canvas (850 x 1100 = approx letter size at 100 dpi)
    w, h = 850, 1100
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Load fonts (fallback to PIL default if truetype not available)
    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_h1 = ImageFont.truetype("arial.ttf", 18)
        font_body = ImageFont.truetype("arial.ttf", 13)
        font_bold = ImageFont.truetype("arialbd.ttf", 13)
        font_small = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font_title = font_h1 = font_body = font_bold = font_small = ImageFont.load_default()

    # Draw based on template variation
    if template_idx == 0:
        # Template A: Modern Blue Header
        draw.rectangle([0, 0, w, 90], fill=(24, 43, 73))
        draw.text((40, 25), "INVOICE", fill=(255, 255, 255), font=font_title)
        draw.text((w - 280, 30), f"Number: {inv_num}", fill=(255, 255, 255), font=font_h1)

        # Vendor & Billed To
        draw.text((40, 120), vendor_name, fill=(15, 23, 42), font=font_bold)
        draw.text((40, 140), vendor_addr, fill=(100, 116, 139), font=font_small)
        draw.text((40, 158), f"Email: {vendor_email}", fill=(100, 116, 139), font=font_small)

        draw.text((w - 300, 120), "Billed To:", fill=(15, 23, 42), font=font_bold)
        draw.text((w - 300, 140), "AcroCorp Global (US-East)", fill=(51, 65, 85), font=font_body)
        draw.text((w - 300, 158), "Attn: Accounts Payable / Finance", fill=(100, 116, 139), font=font_small)

        # Metadata bar
        draw.rectangle([40, 195, w - 40, 235], fill=(241, 245, 249))
        draw.text((50, 206), f"Invoice Date: {inv_date_iso}", fill=(30, 41, 59), font=font_bold)
        draw.text((250, 206), f"Due Date: {due_date_iso}", fill=(30, 41, 59), font=font_bold)
        if po_num:
            draw.text((450, 206), f"PO Number: {po_num}", fill=(30, 41, 59), font=font_bold)
        draw.text((650, 206), f"Currency: {curr_code}", fill=(30, 41, 59), font=font_bold)

    elif template_idx == 1:
        # Template B: Classic Corporate Serif / Monochrome
        draw.text((40, 40), vendor_name.upper(), fill=(15, 23, 42), font=font_h1)
        draw.text((40, 65), vendor_addr, fill=(71, 85, 105), font=font_small)
        draw.text((40, 82), f"Contact: {vendor_email}", fill=(71, 85, 105), font=font_small)

        draw.text((w - 240, 40), "TAX INVOICE", fill=(15, 23, 42), font=font_title)
        draw.line([40, 110, w - 40, 110], fill=(15, 23, 42), width=2)

        draw.text((40, 125), f"Invoice #: {inv_num}", fill=(15, 23, 42), font=font_bold)
        draw.text((40, 145), f"Date of Issue: {inv_date_iso}", fill=(51, 65, 85), font=font_body)
        draw.text((40, 165), f"Payment Due Date: {due_date_iso}", fill=(51, 65, 85), font=font_body)
        if po_num:
            draw.text((40, 185), f"Purchase Order Ref: {po_num}", fill=(51, 65, 85), font=font_body)

        draw.text((w - 300, 125), "Customer Details:", fill=(15, 23, 42), font=font_bold)
        draw.text((w - 300, 145), "AcroCorp Global Operations", fill=(51, 65, 85), font=font_body)
        draw.text((w - 300, 165), "100 Enterprise Way, Suite 400", fill=(100, 116, 139), font=font_small)

    else:
        # Template C: Minimalist Grid Layout
        draw.rectangle([40, 40, w - 40, 130], outline=(203, 213, 225), width=1)
        draw.text((55, 50), vendor_name, fill=(15, 23, 42), font=font_title)
        draw.text((55, 82), f"Vendor Email: {vendor_email} | Address: {vendor_addr}", fill=(100, 116, 139), font=font_small)
        
        draw.text((55, 150), f"INVOICE REFERENCE: {inv_num}", fill=(30, 41, 59), font=font_h1)
        draw.text((55, 180), f"DATE: {inv_date_iso}", fill=(71, 85, 105), font=font_body)
        draw.text((280, 180), f"DUE DATE: {due_date_iso}", fill=(71, 85, 105), font=font_body)
        if po_num:
            draw.text((500, 180), f"PURCHASE ORDER: {po_num}", fill=(71, 85, 105), font=font_body)

    # Line Items Table (Y=260 to Y=600)
    y_table = 260
    draw.rectangle([40, y_table, w - 40, y_table + 30], fill=(226, 232, 240))
    draw.text((50, y_table + 8), "Description", fill=(15, 23, 42), font=font_bold)
    draw.text((470, y_table + 8), "Qty", fill=(15, 23, 42), font=font_bold)
    draw.text((550, y_table + 8), "Unit Price", fill=(15, 23, 42), font=font_bold)
    draw.text((w - 150, y_table + 8), "Amount", fill=(15, 23, 42), font=font_bold)

    y_cur = y_table + 38
    for item in line_items:
        draw.text((50, y_cur), item["description"], fill=(30, 41, 59), font=font_body)
        draw.text((480, y_cur), str(item["quantity"]), fill=(30, 41, 59), font=font_body)
        draw.text((550, y_cur), f"{curr_sym}{item['unit_price']:.2f}", fill=(30, 41, 59), font=font_body)
        draw.text((w - 150, y_cur), f"{curr_sym}{item['amount']:.2f}", fill=(30, 41, 59), font=font_body)
        draw.line([40, y_cur + 24, w - 40, y_cur + 24], fill=(241, 245, 249), width=1)
        y_cur += 32

    # Totals Box
    y_totals = max(y_cur + 30, 460)
    draw.line([w - 320, y_totals, w - 40, y_totals], fill=(203, 213, 225), width=1)
    
    draw.text((w - 310, y_totals + 10), "Subtotal:", fill=(71, 85, 105), font=font_body)
    draw.text((w - 150, y_totals + 10), f"{curr_sym}{subtotal:.2f}", fill=(15, 23, 42), font=font_bold)
    
    draw.text((w - 310, y_totals + 34), f"Tax ({tax_rate*100:.1f}%):", fill=(71, 85, 105), font=font_body)
    draw.text((w - 150, y_totals + 34), f"{curr_sym}{tax:.2f}", fill=(15, 23, 42), font=font_body)
    
    draw.rectangle([w - 320, y_totals + 60, w - 40, y_totals + 95], fill=(241, 245, 249))
    draw.text((w - 310, y_totals + 68), "Total Amount Due:", fill=(15, 23, 42), font=font_bold)
    draw.text((w - 150, y_totals + 68), f"{curr_sym}{total:.2f}", fill=(24, 43, 73), font=font_h1)

    # Footer
    draw.text((40, h - 80), "Payment Terms: Net 30. Remit payments via ACH/Wire.", fill=(100, 116, 139), font=font_small)
    draw.text((40, h - 60), f"Thank you for your business — {vendor_name}", fill=(148, 163, 184), font=font_small)

    # Collect full text representation
    full_text_parts = [
        "INVOICE",
        vendor_name,
        vendor_addr,
        f"Email: {vendor_email}",
        f"Invoice Number: {inv_num}",
        f"Invoice Date: {inv_date_iso}",
        f"Due Date: {due_date_iso}",
    ]
    if po_num:
        full_text_parts.append(f"PO Number: {po_num}")
    full_text_parts.append(f"Currency: {curr_code}")
    for item in line_items:
        full_text_parts.append(f"{item['description']} {item['quantity']} {curr_sym}{item['unit_price']:.2f} {curr_sym}{item['amount']:.2f}")
    full_text_parts.extend([
        f"Subtotal: {curr_sym}{subtotal:.2f}",
        f"Tax: {curr_sym}{tax:.2f}",
        f"Total: {curr_sym}{total:.2f}",
    ])

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
        "full_text": "\n".join(full_text_parts),
    }
    return img, gt

def generate_receipt(idx: int) -> tuple[Image.Image, dict]:
    """Render a thermal-style retail/expense receipt."""
    merchant = random.choice(["Metro Office Supplies", "Express Courier Logistics", "QuickPrint Center", "Airport Cafe & Catering"])
    receipt_num = f"REC-2026-{2000 + idx:04d}"
    date_iso = f"2026-10-{random.randint(1, 28):02d}"
    subtotal = round(random.uniform(15.0, 180.0), 2)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)

    w, h = 450, 750
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_h = ImageFont.truetype("arialbd.ttf", 16)
        font_b = ImageFont.truetype("arial.ttf", 12)
        font_m = ImageFont.truetype("cour.ttf", 12)
    except Exception:
        font_h = font_b = font_m = ImageFont.load_default()

    draw.text((w // 2 - 80, 30), merchant.upper(), fill=(0, 0, 0), font=font_h)
    draw.text((w // 2 - 70, 55), "CUSTOMER RECEIPT", fill=(80, 80, 80), font=font_b)
    draw.line([30, 80, w - 30, 80], fill=(0, 0, 0), width=1)
    
    draw.text((30, 95), f"Receipt: {receipt_num}", fill=(0, 0, 0), font=font_m)
    draw.text((30, 115), f"Date: {date_iso}", fill=(0, 0, 0), font=font_m)
    draw.text((30, 135), "Payment: VISA **** 4892", fill=(0, 0, 0), font=font_m)
    draw.line([30, 160, w - 30, 160], fill=(0, 0, 0), width=1)

    draw.text((30, 180), "Office Supplies & Consumables", fill=(0, 0, 0), font=font_m)
    draw.text((w - 100, 180), f"${subtotal:.2f}", fill=(0, 0, 0), font=font_m)

    draw.line([30, 230, w - 30, 230], fill=(0, 0, 0), width=1)
    draw.text((30, 245), "SUBTOTAL:", fill=(0, 0, 0), font=font_m)
    draw.text((w - 100, 245), f"${subtotal:.2f}", fill=(0, 0, 0), font=font_m)
    draw.text((30, 265), "TAX 8%:", fill=(0, 0, 0), font=font_m)
    draw.text((w - 100, 265), f"${tax:.2f}", fill=(0, 0, 0), font=font_m)
    draw.text((30, 290), "TOTAL PAID:", fill=(0, 0, 0), font=font_h)
    draw.text((w - 100, 290), f"${total:.2f}", fill=(0, 0, 0), font=font_h)

    draw.text((w // 2 - 60, 350), "*** THANK YOU ***", fill=(100, 100, 100), font=font_b)

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
        "full_text": f"{merchant}\nCUSTOMER RECEIPT\nReceipt: {receipt_num}\nDate: {date_iso}\nPayment: VISA **** 4892\nOffice Supplies & Consumables ${subtotal:.2f}\nSUBTOTAL: ${subtotal:.2f}\nTAX 8%: ${tax:.2f}\nTOTAL PAID: ${total:.2f}\nTHANK YOU",
    }
    return img, gt

def generate_contract(idx: int) -> tuple[Image.Image, dict]:
    """Render a formal legal contract page."""
    w, h = 850, 1100
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_h = ImageFont.truetype("arialbd.ttf", 20)
        font_b = ImageFont.truetype("times.ttf", 13)
    except Exception:
        font_h = font_b = ImageFont.load_default()

    draw.text((150, 50), "NON-DISCLOSURE AND MUTUAL CONFIDENTIALITY AGREEMENT", fill=(0, 0, 0), font=font_h)
    draw.line([50, 85, w - 50, 85], fill=(0, 0, 0), width=1)
    
    text = f"""This Non-Disclosure Agreement ("Agreement") is entered into as of October {idx+1}, 2026, by and between
AcroCorp Global Enterprises LLC, with offices at 100 Enterprise Way ("Disclosing Party"), and
Partner Services Group Inc ("Receiving Party").

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
AcroCorp Global Enterprises LLC: ______________________      Date: 2026-10-{idx+1:02d}
Partner Services Group Inc:      ______________________      Date: 2026-10-{idx+1:02d}
"""
    y = 120
    for line in text.split("\n"):
        draw.text((60, y), line, fill=(20, 20, 20), font=font_b)
        y += 24

    gt = {
        "document_type": "contract",
        "vendor": "Partner Services Group Inc",
        "invoice_number": f"NDA-2026-{idx:03d}",
        "invoice_date": f"2026-10-{idx+1:02d}",
        "due_date": None,
        "po_number": None,
        "currency": None,
        "subtotal": 0.0,
        "tax": 0.0,
        "total": 0.0,
        "line_items": [],
        "full_text": text.strip(),
    }
    return img, gt

def generate_purchase_order(idx: int) -> tuple[Image.Image, dict]:
    """Render a formal Purchase Order."""
    w, h = 850, 1100
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font_h = ImageFont.truetype("arialbd.ttf", 22)
        font_b = ImageFont.truetype("arial.ttf", 13)
        font_bold = ImageFont.truetype("arialbd.ttf", 13)
    except Exception:
        font_h = font_b = font_bold = ImageFont.load_default()

    draw.text((50, 40), "PURCHASE ORDER", fill=(15, 23, 42), font=font_h)
    draw.text((w - 250, 45), f"P.O. #: PO-2026-{7000+idx}", fill=(15, 23, 42), font=font_bold)
    draw.line([50, 80, w - 50, 80], fill=(200, 200, 200), width=2)
    
    draw.text((50, 100), "ISSUED BY: AcroCorp Procurement", fill=(50, 50, 50), font=font_b)
    draw.text((50, 120), "100 Enterprise Way, Suite 400", fill=(100, 100, 100), font=font_b)
    
    vendor = VENDORS[idx % len(VENDORS)][0]
    draw.text((w - 300, 100), f"VENDOR: {vendor}", fill=(50, 50, 50), font=font_b)
    draw.text((w - 300, 120), "Approved Corporate Supplier", fill=(100, 100, 100), font=font_b)

    draw.text((50, 170), f"Order Date: 2026-10-12 | Delivery Terms: FOB Destination | Payment: Net 45", fill=(30, 30, 30), font=font_bold)

    y = 220
    draw.rectangle([50, y, w - 50, y + 25], fill=(230, 235, 240))
    draw.text((60, y + 5), "Item / Scope of Work", fill=(0, 0, 0), font=font_bold)
    draw.text((w - 150, y + 5), "Est. Total", fill=(0, 0, 0), font=font_bold)

    items = [("Enterprise Software License Allocation Q4", 8500.00), ("Implementation Services & Onboarding", 3500.00)]
    y += 35
    for desc, amt in items:
        draw.text((60, y), desc, fill=(40, 40, 40), font=font_b)
        draw.text((w - 150, y), f"${amt:.2f}", fill=(40, 40, 40), font=font_b)
        y += 28

    total = sum(amt for _, amt in items)
    draw.text((w - 300, y + 30), f"AUTHORIZED TOTAL: ${total:.2f}", fill=(0, 0, 0), font=font_bold)

    gt = {
        "document_type": "purchase_order",
        "vendor": vendor,
        "invoice_number": None,
        "invoice_date": "2026-10-12",
        "due_date": None,
        "po_number": f"PO-2026-{7000+idx}",
        "currency": "USD",
        "subtotal": total,
        "tax": 0.0,
        "total": total,
        "line_items": [{"description": d, "quantity": 1, "unit_price": a, "amount": a} for d, a in items],
        "full_text": f"PURCHASE ORDER\nP.O. #: PO-2026-{7000+idx}\nISSUED BY: AcroCorp Procurement\nVENDOR: {vendor}\nOrder Date: 2026-10-12\nEnterprise Software License Allocation Q4 $8500.00\nImplementation Services & Onboarding $3500.00\nAUTHORIZED TOTAL: ${total:.2f}",
    }
    return img, gt

def main():
    print(f"Generating synthetic OCR benchmark dataset in {DATA_DIR}...")
    dataset = []

    # 1. Generate 80 Invoices (Clean + Degraded)
    # Total invoice variations: 80 clean + 80 degraded = 160 invoice images
    degradation_types = ["skew", "blur", "noise_jpeg", "low_res", "contrast", "rotated_90"]
    
    for i in range(80):
        template_idx = i % 3
        img_clean, gt = generate_invoice(i, template_idx)
        
        doc_id_clean = f"inv_{i:03d}_clean"
        img_path_clean = DATA_DIR / f"{doc_id_clean}.png"
        gt_path_clean = DATA_DIR / f"{doc_id_clean}.json"
        
        img_clean.save(img_path_clean)
        gt_clean = dict(gt)
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
        gt_deg = dict(gt)
        gt_deg["doc_id"] = doc_id_deg
        gt_deg["is_degraded"] = True
        gt_deg["degradation"] = deg_type
        gt_deg["image_path"] = str(img_path_deg)
        with open(gt_path_deg, "w", encoding="utf-8") as f:
            json.dump(gt_deg, f, indent=2)
        dataset.append(gt_deg)

    # 2. Generate 10 Receipts
    for i in range(10):
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

    # 3. Generate 10 Contracts
    for i in range(10):
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

    # 4. Generate 10 Purchase Orders
    for i in range(10):
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

    # 5. Deterministic Split (Train: 50%, Dev: 25%, Test: 25%)
    # Stratified by document type and degradation status
    rng = random.Random(SEED)
    rng.shuffle(dataset)

    train_ids = []
    dev_ids = []
    test_ids = []

    # Group by category (e.g. invoice_clean, invoice_degraded, receipt, contract, po)
    groups = {}
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
            "test": len(test_ids)
        },
        "train": sorted(train_ids),
        "dev": sorted(dev_ids),
        "test": sorted(test_ids)
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
