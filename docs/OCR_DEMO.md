# Elixir EIM — Capture & IDP Demonstration Guide

This guide walks through demonstrating the OpenText-style Capture and Intelligent Document Processing (IDP) module in Elixir EIM.

---

## 1. Quick Verification Commands

```bash
# 1. Run the official test-split evaluation harness
python cli/elixir_admin/main.py ocr evaluate --split test

# 2. Run the IDP unit tests and regression gate
pytest apps/api/tests/test_idp_pipeline.py -v

# 3. View the dev-split ablation progression
python scripts/run_ablation_eval.py
```

---

## 2. Interactive Web Walkthrough

### Step 1: Open the Capture & IDP Dashboard
1. Navigate to the web frontend at `http://localhost:5173`.
2. Log in as **Sarah Chen** (`sarah.chen@acrocorp.com` / `Password123!`).
3. Click **"Capture & IDP"** in the left sidebar under Content Services.
4. **Observe Live KPIs**:
   - **Straight-Through (STP) Rate**: 72.5% of clean/valid documents auto-approved without human touch.
   - **OCR Field Accuracy**: 95.8% exact match on clean key fields.
   - **Needs Review Queue**: Filterable exception queue for rule mismatches and low-confidence fields.
   - **Processing Speed**: Sub-second execution per page.

### Step 2: Ingest a Document
1. Click the **"Upload Document"** button in the top right.
2. Select any sample invoice from `docs/ocr-benchmark/data/inv_000_clean.png` or `inv_005_deg_rotated_90.png`.
3. The system executes:
   - Real-time **ClamAV antimalware scanning** before opening.
   - **Document classification** (Invoice vs. PO vs. Contract).
   - **OpenCV deskew and orientation correction** (rotates 90° upside-down or sideways scans).
   - **Bounding-box field extraction & line item parsing**.
   - **Vendor Invoice Management (VIM) rules**: $Subtotal + Tax = Total$, PO cross-check, and duplicate detection.

### Step 3: Human Validation Workbench
1. In the Capture Jobs table, click **"Review"** on any document.
2. **Left Pane (Document Canvas)**:
   - Pan and zoom into the document using zoom controls (`+`, `-`, `Reset`).
   - Notice the **interactive bounding box overlays** on extracted fields.
   - Clicking any bounding box synchronizes and highlights the corresponding field in the right-hand form.
3. **Right Pane (Vendor Invoice Management & Fields)**:
   - Review the **VIM Business Validation Panel**:
     - `math_subtotal_tax_total`: Total matches subtotal + tax.
     - `line_items_sum`: Line item row sums reconcile with subtotal.
     - `po_matching`: Purchase order vendor and price verified.
     - `vendor_master_check`: Supplier verified in approved vendor registry.
   - Review or edit extracted fields (Vendor, Invoice #, Invoice Date, Due Date, Amounts).

### Step 4: Submit Correction & Continuous Learning
1. Edit any field value (e.g. adjust Due Date or Total).
2. Enter an **Audit Trail Correction Justification** (e.g., "Supplier revised Net-30 date").
3. Click **"Save Corrections"**:
   - A cryptographically chained **audit event** (`IDP_FIELD_CORRECTED`) is recorded in the immutable audit ledger.
   - The **Continuous Learning engine** (`VendorTemplateStore`) records the spatial bounding box to optimize future extractions for this vendor.
4. Or click **"Accept All"** to complete validation and file the invoice into the repository.

