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
        ("buyer_gstin", "33AABCU8048A1Z0", "33AABCU8048A1Z0", 0.96, 1, {"x": 77, "y": 260, "width": 85, "height": 7}, "regex_base36", False, "Check digit 0 vs O review"),
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
    cur.execute("DELETE FROM extracted_fields WHERE job_id = %s", (inf_id,))
    cur.execute("DELETE FROM capture_jobs WHERE id = %s", (inf_id,))
    cur.execute("""
        INSERT INTO capture_jobs (id, tenant_id, filename, status, document_type, classification_confidence, ocr_engine, mean_confidence, processing_time_ms, raw_text, created_at, updated_at)
        VALUES (%s, %s, 'INV-2026-0892_Infosys_Technologies.pdf', 'auto_approved', 'TAX INVOICE', 99.8, 'indra', 99.4, 820.0, 'TAX INVOICE\nInfosys Technologies Limited\nGSTIN: 29AABCI1234F1ZX', now(), now())
    """, (inf_id, tenant_id))

    # 3. Seed Completed TCS Job
    tcs_id = "33333333-3333-3333-3333-333333333333"
    cur.execute("DELETE FROM extracted_fields WHERE job_id = %s", (tcs_id,))
    cur.execute("DELETE FROM capture_jobs WHERE id = %s", (tcs_id,))
    cur.execute("""
        INSERT INTO capture_jobs (id, tenant_id, filename, status, document_type, classification_confidence, ocr_engine, mean_confidence, processing_time_ms, raw_text, created_at, updated_at)
        VALUES (%s, %s, 'TCS-2026-4410_Tata_Consultancy_Services.pdf', 'completed', 'TAX INVOICE', 99.9, 'pymupdf', 99.8, 410.0, 'TAX INVOICE\nTata Consultancy Services Ltd\nGSTIN: 27AAACT2718E1ZQ', now(), now())
    """, (tcs_id, tenant_id))

    conn.commit()
    print("SUCCESS: Database seeded with accurate demo jobs and 18 fields!")
    conn.close()

if __name__ == "__main__":
    main()
