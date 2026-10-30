"""Seed high-fidelity demo jobs and extracted fields to PostgreSQL."""
import json
import psycopg

def main():
    conn = psycopg.connect("postgresql://elixir:elixir_secure_pass@localhost:5432/elixir_eim")
    cur = conn.cursor()
    tenant_id = "11111111-1111-1111-1111-111111111111"

    # 1. Update or Insert Sri Balaji Computers
    sbc_id = "6884a71d-a246-427b-8946-fe674242dd41"
    sbc_raw = """TAX INVOICE / CASH BILL
SRI BALAJI COMPUTERS
72, SARATHY NAGAR, KAGITHAPATTARI
VELLORE - 632012
GSTIN/UIN: 33AAQPK8576K1ZY
State Name: Tamil Nadu, Code: 33
E-Mail: bcitvir@gmail.com

Buyer (Bill to):
S2 INTEGRATORS PVT LTD
547, ANNA SALAI, NANDANAM, CHENNAI
GSTIN/UIN: 33AABCU8048A1Z0
State Name: Tamil Nadu, Code: 33

Invoice No: SBC/0590/2026-27      Dated: 5-Jun-26
Delivery Note:                     Mode/Terms of Payment:
Reference No. & Date:              Other References:
Dispatch Doc No:                   Delivery Note Date:
Dispatched through:                Destination:
Terms of Delivery:

Sl. Particulars                      HSN/SAC   Quantity  Rate per     Amount
1   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    Mr. RISHMA, LENOVO T14
2   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    Mr. SYED IDROSE, DELL LATITUDE 5411
3   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    FAZIL, DELL LATITUDE 5411
4   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    RAGA PRIYA, DELL LATITUDE 5411
5   LAPTOP RENTAL                    997315    -         3,500.00     3,500.00
    Ms. RENUGADEVI SALEM, LENOVO IDEAPAD 3

                                     SGST 9%                          1,575.00
                                     CGST 9%                          1,575.00
                                     Total                           20,650.00

Amount Chargeable (in words):
INR Twenty Thousand Six Hundred Fifty Only
"""

    cur.execute("""
        UPDATE capture_jobs 
        SET filename = 'SBC-0590_Sri_Balaji_Computers_TamilNadu.pdf',
            status = 'needs_review',
            document_type = 'TAX INVOICE / CASH BILL',
            classification_confidence = 99.1,
            ocr_engine = 'tesseract',
            mean_confidence = 94.2,
            processing_time_ms = 1240.5,
            raw_text = %s
        WHERE id = %s
    """, (sbc_raw, sbc_id))

    # Re-seed extracted fields for Sri Balaji
    cur.execute("DELETE FROM extracted_fields WHERE job_id = %s", (sbc_id,))
    fields = [
        ("supplier_gstin", "33AAQPK8576K1ZY", "33AAQPK8576K1ZY", 0.96, 1, {"x": 77, "y": 115, "width": 85, "height": 7}, "regex_base36", True, None),
        ("buyer_gstin", "33AABCU8048A1Z0", "33AABCU8048A1Z0", 0.96, 1, {"x": 77, "y": 260, "width": 85, "height": 7}, "regex_base36", False, "INTENTIONAL_INVALID: OCR digit confusion (Expected 'O', OCR read '0')"),
        ("supplier_name", "SRI BALAJI COMPUTERS", "SRI BALAJI COMPUTERS", 0.88, 1, {"x": 77, "y": 70, "width": 110, "height": 8}, "layout_header", True, None),
        ("buyer_name", "S2 INTEGRATORS PVT LTD", "S2 INTEGRATORS PVT LTD", 0.85, 1, {"x": 77, "y": 220, "width": 115, "height": 8}, "layout_header", True, None),
        ("supplier_address", "72, SARATHY NAGAR, KAGITHAPATTARI, VELLORE - 632012", "72, SARATHY NAGAR, KAGITHAPATTARI, VELLORE - 632012", 0.82, 1, {"x": 77, "y": 80, "width": 120, "height": 15}, "layout_address", True, None),
        ("buyer_address", "547, ANNA SALAI, NANDANAM, CHENNAI", "547, ANNA SALAI, NANDANAM, CHENNAI", 0.80, 1, {"x": 77, "y": 235, "width": 120, "height": 15}, "layout_address", True, None),
        ("invoice_number", "SBC/0590/2026-27", "SBC/0590/2026-27", 0.92, 1, {"x": 238, "y": 160, "width": 50, "height": 7}, "regex_labeled", True, None),
        ("invoice_date", "2026-06-05", "2026-06-05", 0.94, 1, {"x": 318, "y": 160, "width": 40, "height": 7}, "regex_labeled", True, None),
        ("currency", "INR", "INR", 0.95, 1, None, "inferred_gstin", True, None),
        ("contact_details", "bcitvir@gmail.com", "bcitvir@gmail.com", 0.95, 1, {"x": 77, "y": 140, "width": 70, "height": 7}, "regex_email", True, None),
        ("subtotal", "17500.00", "17500.00", 0.98, 1, {"x": 360, "y": 250, "width": 40, "height": 7}, "line_items_sum", True, None),
        ("sgst_amount", "1575.00", "1575.00", 0.97, 1, {"x": 360, "y": 270, "width": 40, "height": 7}, "regex_tax", True, None),
        ("cgst_amount", "1575.00", "1575.00", 0.97, 1, {"x": 360, "y": 285, "width": 40, "height": 7}, "regex_tax", True, None),
        ("total", "20650.00", "20650.00", 0.99, 1, {"x": 360, "y": 315, "width": 45, "height": 8}, "math_reconciliation", True, None),
        ("state_code", "33", "33", 0.99, 1, None, "gstin_prefix", True, None),
        ("state_name", "Tamil Nadu", "Tamil Nadu", 0.99, 1, None, "state_lookup", True, None),
    ]
    for f in fields:
        norm_val = json.dumps(f[2]) if f[2] is not None else None
        bbox_val = json.dumps(f[5]) if f[5] else None
        cur.execute("""
            INSERT INTO extracted_fields (id, tenant_id, job_id, field_name, field_value, normalized_value, confidence, page, bbox, extraction_method, is_valid, error_message, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        """, (tenant_id, sbc_id, f[0], f[1], norm_val, f[3], f[4], bbox_val, f[6], f[7], f[8]))

    # 2. Seed Auto-Approved Infosys Job
    inf_id = "22222222-2222-2222-2222-222222222222"
    inf_raw = """TAX INVOICE
INFOSYS TECHNOLOGIES LIMITED
Electronics City, Hosur Road, Bangalore - 560100, Karnataka
GSTIN/UIN: 29AABCI1234F1ZX | State Code: 29 | Contact: billing@infosys.com

Bill To:
ACROCORP GLOBAL ENTERPRISES
Plot 44, OMR IT Expressway, Chennai - 600096, Tamil Nadu
GSTIN/UIN: 33AABCA9876C1ZQ | State Code: 33

Invoice No: INV-2026-0892              Invoice Date: 18-May-2026
PO Number: PO-2026-0442                Due Date: 17-Jun-2026
Payment Terms: Net 30 Days             Currency: INR

Sl. Description                         HSN/SAC    Qty     Rate (INR)     Amount (INR)
1   Cloud Architecture Consulting       998313     1       120,000.00     120,000.00
2   DevOps CI/CD Implementation         998314     1        65,000.00      65,000.00

Subtotal:                                                                 185,000.00
Integrated GST (IGST 18%):                                                 33,300.00
Total Amount Payable:                                                     218,300.00

Amount in Words: INR Two Lakh Eighteen Thousand Three Hundred Only
Bank Details: State Bank of India, A/C: 38920192831, IFSC: SBIN0004120
"""
    cur.execute("DELETE FROM extracted_fields WHERE job_id = %s", (inf_id,))
    cur.execute("DELETE FROM capture_jobs WHERE id = %s", (inf_id,))
    cur.execute("""
        INSERT INTO capture_jobs (id, tenant_id, filename, status, document_type, classification_confidence, ocr_engine, mean_confidence, processing_time_ms, raw_text, created_at, updated_at)
        VALUES (%s, %s, 'INV-2026-0892_Infosys_Technologies.pdf', 'auto_approved', 'TAX INVOICE', 99.8, 'indra', 99.4, 820.0, %s, now(), now())
    """, (inf_id, tenant_id, inf_raw))

    inf_fields = [
        ("supplier_gstin", "29AABCI1234F1ZX", "29AABCI1234F1ZX", 0.99, 1, {"x": 75, "y": 95, "width": 95, "height": 10}, "regex_base36", True, None),
        ("buyer_gstin", "33AABCA9876C1ZQ", "33AABCA9876C1ZQ", 0.99, 1, {"x": 75, "y": 200, "width": 95, "height": 10}, "regex_base36", True, None),
        ("supplier_name", "INFOSYS TECHNOLOGIES LIMITED", "INFOSYS TECHNOLOGIES LIMITED", 0.98, 1, {"x": 75, "y": 55, "width": 160, "height": 12}, "layout_header", True, None),
        ("buyer_name", "ACROCORP GLOBAL ENTERPRISES", "ACROCORP GLOBAL ENTERPRISES", 0.97, 1, {"x": 75, "y": 165, "width": 150, "height": 12}, "layout_header", True, None),
        ("supplier_address", "Electronics City, Hosur Road, Bangalore - 560100, Karnataka", "Electronics City, Hosur Road, Bangalore - 560100, Karnataka", 0.96, 1, {"x": 75, "y": 72, "width": 220, "height": 15}, "layout_address", True, None),
        ("buyer_address", "Plot 44, OMR IT Expressway, Chennai - 600096, Tamil Nadu", "Plot 44, OMR IT Expressway, Chennai - 600096, Tamil Nadu", 0.96, 1, {"x": 75, "y": 180, "width": 210, "height": 15}, "layout_address", True, None),
        ("invoice_number", "INV-2026-0892", "INV-2026-0892", 0.99, 1, {"x": 260, "y": 240, "width": 65, "height": 10}, "regex_labeled", True, None),
        ("invoice_date", "2026-05-18", "2026-05-18", 0.99, 1, {"x": 420, "y": 240, "width": 55, "height": 10}, "regex_labeled", True, None),
        ("po_number", "PO-2026-0442", "PO-2026-0442", 0.98, 1, {"x": 260, "y": 260, "width": 65, "height": 10}, "regex_labeled", True, None),
        ("due_date", "2026-06-17", "2026-06-17", 0.97, 1, {"x": 420, "y": 260, "width": 55, "height": 10}, "regex_labeled", True, None),
        ("currency", "INR", "INR", 0.99, 1, None, "inferred_gstin", True, None),
        ("contact_details", "billing@infosys.com", "billing@infosys.com", 0.99, 1, {"x": 220, "y": 95, "width": 90, "height": 10}, "regex_email", True, None),
        ("subtotal", "185000.00", "185000.00", 0.99, 1, {"x": 410, "y": 380, "width": 55, "height": 10}, "line_items_sum", True, None),
        ("igst_amount", "33300.00", "33300.00", 0.99, 1, {"x": 410, "y": 405, "width": 55, "height": 10}, "regex_tax", True, None),
        ("total", "218300.00", "218300.00", 0.99, 1, {"x": 410, "y": 435, "width": 60, "height": 12}, "math_reconciliation", True, None),
        ("state_code", "29", "29", 0.99, 1, None, "gstin_prefix", True, None),
        ("state_name", "Karnataka", "Karnataka", 0.99, 1, None, "state_lookup", True, None),
    ]
    for f in inf_fields:
        norm_val = json.dumps(f[2]) if f[2] is not None else None
        bbox_val = json.dumps(f[5]) if f[5] else None
        cur.execute("""
            INSERT INTO extracted_fields (id, tenant_id, job_id, field_name, field_value, normalized_value, confidence, page, bbox, extraction_method, is_valid, error_message, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        """, (tenant_id, inf_id, f[0], f[1], norm_val, f[3], f[4], bbox_val, f[6], f[7], f[8]))

    # 3. Seed Completed TCS Job
    tcs_id = "33333333-3333-3333-3333-333333333333"
    tcs_raw = """TAX INVOICE
TATA CONSULTANCY SERVICES LTD
TCS House, Raveline Street, Fort, Mumbai - 400001, Maharashtra
GSTIN/UIN: 27AAACT2718E1ZM | State Code: 27 | Contact: accounts@tcs.com

Bill To:
ACROCORP GLOBAL ENTERPRISES
Plot 44, OMR IT Expressway, Chennai - 600096, Tamil Nadu
GSTIN/UIN: 33AABCA9876C1ZQ | State Code: 33

Invoice No: TCS-2026-4410              Invoice Date: 22-Apr-2026
PO Number: PO-2026-0198                Due Date: 22-May-2026
Payment Terms: Net 30 Days             Currency: INR

Sl. Description                         HSN/SAC    Qty     Rate (INR)     Amount (INR)
1   Enterprise Security Architecture    998315     1       250,000.00     250,000.00
2   ISO 27001 Audit & Penetration Test  998316     1       170,000.00     170,000.00

Subtotal:                                                                 420,000.00
Integrated GST (IGST 18%):                                                 75,600.00
Total Amount Payable:                                                     495,600.00

Amount in Words: INR Four Lakh Ninety Five Thousand Six Hundred Only
Bank Details: HDFC Bank, A/C: 50200019283741, IFSC: HDFC0000060
"""
    cur.execute("DELETE FROM extracted_fields WHERE job_id = %s", (tcs_id,))
    cur.execute("DELETE FROM capture_jobs WHERE id = %s", (tcs_id,))
    cur.execute("""
        INSERT INTO capture_jobs (id, tenant_id, filename, status, document_type, classification_confidence, ocr_engine, mean_confidence, processing_time_ms, raw_text, created_at, updated_at)
        VALUES (%s, %s, 'TCS-2026-4410_Tata_Consultancy_Services.pdf', 'completed', 'TAX INVOICE', 99.9, 'pymupdf', 99.8, 410.0, %s, now(), now())
    """, (tcs_id, tenant_id, tcs_raw))

    tcs_fields = [
        ("supplier_gstin", "27AAACT2718E1ZM", "27AAACT2718E1ZM", 0.99, 1, {"x": 75, "y": 95, "width": 95, "height": 10}, "regex_base36", True, None),
        ("buyer_gstin", "33AABCA9876C1ZQ", "33AABCA9876C1ZQ", 0.99, 1, {"x": 75, "y": 200, "width": 95, "height": 10}, "regex_base36", True, None),
        ("supplier_name", "TATA CONSULTANCY SERVICES LTD", "TATA CONSULTANCY SERVICES LTD", 0.99, 1, {"x": 75, "y": 55, "width": 170, "height": 12}, "layout_header", True, None),
        ("buyer_name", "ACROCORP GLOBAL ENTERPRISES", "ACROCORP GLOBAL ENTERPRISES", 0.98, 1, {"x": 75, "y": 165, "width": 150, "height": 12}, "layout_header", True, None),
        ("supplier_address", "TCS House, Raveline Street, Fort, Mumbai - 400001, Maharashtra", "TCS House, Raveline Street, Fort, Mumbai - 400001, Maharashtra", 0.97, 1, {"x": 75, "y": 72, "width": 240, "height": 15}, "layout_address", True, None),
        ("buyer_address", "Plot 44, OMR IT Expressway, Chennai - 600096, Tamil Nadu", "Plot 44, OMR IT Expressway, Chennai - 600096, Tamil Nadu", 0.97, 1, {"x": 75, "y": 180, "width": 210, "height": 15}, "layout_address", True, None),
        ("invoice_number", "TCS-2026-4410", "TCS-2026-4410", 0.99, 1, {"x": 260, "y": 240, "width": 65, "height": 10}, "regex_labeled", True, None),
        ("invoice_date", "2026-04-22", "2026-04-22", 0.99, 1, {"x": 420, "y": 240, "width": 55, "height": 10}, "regex_labeled", True, None),
        ("po_number", "PO-2026-0198", "PO-2026-0198", 0.99, 1, {"x": 260, "y": 260, "width": 65, "height": 10}, "regex_labeled", True, None),
        ("due_date", "2026-05-22", "2026-05-22", 0.98, 1, {"x": 420, "y": 260, "width": 55, "height": 10}, "regex_labeled", True, None),
        ("currency", "INR", "INR", 0.99, 1, None, "inferred_gstin", True, None),
        ("contact_details", "accounts@tcs.com", "accounts@tcs.com", 0.99, 1, {"x": 220, "y": 95, "width": 80, "height": 10}, "regex_email", True, None),
        ("subtotal", "420000.00", "420000.00", 0.99, 1, {"x": 410, "y": 380, "width": 55, "height": 10}, "line_items_sum", True, None),
        ("igst_amount", "75600.00", "75600.00", 0.99, 1, {"x": 410, "y": 405, "width": 55, "height": 10}, "regex_tax", True, None),
        ("total", "495600.00", "495600.00", 0.99, 1, {"x": 410, "y": 435, "width": 60, "height": 12}, "math_reconciliation", True, None),
        ("state_code", "27", "27", 0.99, 1, None, "gstin_prefix", True, None),
        ("state_name", "Maharashtra", "Maharashtra", 0.99, 1, None, "state_lookup", True, None),
    ]
    for f in tcs_fields:
        norm_val = json.dumps(f[2]) if f[2] is not None else None
        bbox_val = json.dumps(f[5]) if f[5] else None
        cur.execute("""
            INSERT INTO extracted_fields (id, tenant_id, job_id, field_name, field_value, normalized_value, confidence, page, bbox, extraction_method, is_valid, error_message, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        """, (tenant_id, tcs_id, f[0], f[1], norm_val, f[3], f[4], bbox_val, f[6], f[7], f[8]))

    conn.commit()
    print("SUCCESS: Database seeded with accurate demo jobs and 18 fields!")
    conn.close()

if __name__ == "__main__":
    main()
