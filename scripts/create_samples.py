import os
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF

samples_dir = os.path.join(os.getcwd(), "docs", "demo-samples")
os.makedirs(samples_dir, exist_ok=True)

# 1. EICAR Test String
eicar_path = os.path.join(samples_dir, "eicar_test.txt")
eicar_content = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
with open(eicar_path, "w", encoding="utf-8") as f:
    f.write(eicar_content)
print(f"Created {eicar_path}")

# 2. Invoice Image with clear text for OCR
invoice_path = os.path.join(samples_dir, "invoice_sample.png")
img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
draw = ImageDraw.Draw(img)

# Draw structured invoice text
lines = [
    ("INVOICE", 40, (15, 23, 42)),
    ("ACME CORPORATE SOLUTIONS LTD", 20, (51, 65, 85)),
    ("100 Enterprise Way, Suite 400, New York, NY 10001", 14, (100, 116, 139)),
    ("", 14, (0, 0, 0)),
    ("Invoice Number: INV-2026-9842", 18, (15, 23, 42)),
    ("Invoice Date: October 28, 2026", 16, (30, 41, 59)),
    ("Payment Terms: Net 30 Days", 16, (30, 41, 59)),
    ("Department: Finance", 16, (30, 41, 59)),
    ("Classification: CONFIDENTIAL", 16, (185, 28, 28)),
    ("", 14, (0, 0, 0)),
    ("Billed To: AcroCorp Finance Operations", 16, (15, 23, 42)),
    ("Attn: Raj Patel (raj.patel@acrocorp.com)", 14, (71, 85, 105)),
    ("--------------------------------------------------------------------------------", 14, (203, 213, 225)),
    ("Line Item Description                                     Qty    Unit Price     Total", 14, (15, 23, 42)),
    ("--------------------------------------------------------------------------------", 14, (203, 213, 225)),
    ("Enterprise Information Management Cloud Suite v1.0          1    $4,500.00    $4,500.00", 14, (51, 65, 85)),
    ("ClamAV Malware Protection & Content Security Scanner        1    $1,200.00    $1,200.00", 14, (51, 65, 85)),
    ("Tesseract Optical Character Recognition (OCR) Engine        1    $1,000.00    $1,000.00", 14, (51, 65, 85)),
    ("--------------------------------------------------------------------------------", 14, (203, 213, 225)),
    ("Subtotal:                                                                    $6,700.00", 15, (15, 23, 42)),
    ("Tax (0.00% Exempt):                                                             $0.00", 14, (100, 116, 139)),
    ("TOTAL AMOUNT DUE:                                                           $6,700.00", 18, (15, 23, 42)),
    ("", 14, (0, 0, 0)),
    ("Remittance Instructions: Bank of America, Wire Routing #026009593, Acct #448920194", 13, (100, 116, 139)),
    ("Confidential document. Unauthorized reproduction or redistribution is prohibited.", 12, (148, 163, 184)),
]

y = 40
for text_line, font_size, color in lines:
    if text_line:
        # Use default bitmap font for crisp rendering
        draw.text((50, y), text_line, fill=color)
    y += 32

img.save(invoice_path)
print(f"Created {invoice_path}")

# 3. Multi-page PDF Contract
pdf_path = os.path.join(samples_dir, "multi_page_contract.pdf")
doc = fitz.open()

# Page 1
page1 = doc.new_page(width=595, height=842)
text1 = """MASTER SERVICES AND DATA PROCESSING AGREEMENT

Contract Reference: MSA-2026-ELX-001
Effective Date: October 28, 2026
Parties: AcroCorp Enterprises LLC ("Client") and Elixir Information Management Inc ("Provider")

1. RECITALS
WHEREAS, Provider specializes in enterprise information management, cryptographic audit ledgers,
automated workflow processing, and content archival solutions;
WHEREAS, Client wishes to deploy Provider's Elixir EIM 1.0 platform for document retention,
full-text discovery, and policy enforcement across corporate departments including Finance and HR.

2. CLASSIFICATION AND SECURITY POLICIES
All data processed under this Agreement shall adhere strictly to Client's Security Classification Scheme:
- PUBLIC: Marketing, external whitepapers, and public bulletins.
- INTERNAL: General corporate policies, standard operating procedures, and team announcements.
- CONFIDENTIAL: Department-specific operational records, invoices, financial ledger entries.
- RESTRICTED: Sensitive personnel records, executive compensation, and trade secrets.

3. DATA RETENTION AND LEGAL HOLD OBLIGATIONS
Pursuant to corporate retention policy FIN-REC-07, financial invoices and transaction ledgers must be
retained for seven (7) years following completion of the fiscal year. In the event of a Legal Hold,
all destruction workflows are strictly suspended until formal lift authorization is audited.
"""
page1.insert_textbox(fitz.Rect(50, 60, 545, 780), text1, fontsize=11)

# Page 2
page2 = doc.new_page(width=595, height=842)
text2 = """EXHIBIT A: AUDIT VERIFICATION AND TECHNICAL STANDARDS

1. CRYPTOGRAPHIC HASH CHAINING
Provider warrants that all mutating operations across documents, legal holds, and workflow decisions
shall be written to an immutable PostgreSQL append-only audit ledger. Each entry shall contain:
- Monotonically increasing sequence number
- SHA-256 hash chaining tying current record payload to prior record digest
- Contextual metadata including tenant ID, actor identity, timestamp, and decision outcome.

2. OPTICAL CHARACTER RECOGNITION (OCR) SPECIFICATIONS
Provider's automated ingestion pipeline shall process uploaded PDFs and high-resolution raster images
using Tesseract v5 and PyMuPDF. Extracted text layers shall be indexed into PostgreSQL full-text
search tsvectors with GIN indexing to facilitate sub-second query retrieval.

3. GOVERNING LAW AND SIGNATURES
This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware.

IN WITNESS WHEREOF, the parties hereto have executed this Agreement as of the Effective Date.

For AcroCorp Enterprises LLC:                   For Elixir Information Management Inc:
Sarah Chen                                      Harrish Sebastin
Head of Records & Compliance                    Principal Enterprise Architect
"""
page2.insert_textbox(fitz.Rect(50, 60, 545, 780), text2, fontsize=11)

doc.save(pdf_path)
doc.close()
print(f"Created {pdf_path}")
