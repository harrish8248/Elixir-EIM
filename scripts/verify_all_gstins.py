from apps.api.app.content.idp.gstin import validate_gstin, compute_gstin_check_char

# All GSTINs from seed_demo_jobs.py, demo_store.py, and validation.py
gstin_inventory = [
    # From scripts/seed_demo_jobs.py
    ("scripts/seed_demo_jobs.py", "Sri Balaji Computers (Supplier)", "33AAQPK8576K1ZY", False),
    ("scripts/seed_demo_jobs.py", "S2 Integrators (Buyer)", "33AABCU8048A1Z0", True),  # INTENTIONAL_INVALID: OCR digit confusion
    ("scripts/seed_demo_jobs.py", "Infosys Technologies (Supplier)", "29AABCI1234F1ZX", False),
    ("scripts/seed_demo_jobs.py", "AcroCorp Global (Buyer)", "33AABCA9876C1ZQ", False),
    ("scripts/seed_demo_jobs.py", "Tata Consultancy Services (Supplier)", "27AAACT2718E1ZM", False),

    # From demo_store.py (6 earlier seeded capture jobs/fields)
    ("apps/api/app/platform/demo_store.py", "Sri Balaji Computers (Supplier)", "33AAQPK8576K1ZY", False),
    ("apps/api/app/platform/demo_store.py", "S2 Integrators (Buyer)", "33AABCU8048A1Z0", True),  # INTENTIONAL_INVALID: OCR digit confusion
    ("apps/api/app/platform/demo_store.py", "Infosys Technologies (Supplier)", "29AABCI1234F1ZX", False),
    ("apps/api/app/platform/demo_store.py", "AcroCorp India (Buyer)", "27AABCA9876M1ZY", False),
    ("apps/api/app/platform/demo_store.py", "Tata Consultancy Services (Supplier)", "27AAPFU0939F1ZV", False),
    ("apps/api/app/platform/demo_store.py", "Delhi Telecom (Buyer)", "07AAACH2345J1ZQ", False),

    # From validation.py (SEEDED_VENDOR_MASTER)
    ("apps/api/app/content/idp/validation.py", "TCS Master Catalog", "27AAACT2718E1ZM", False),
    ("apps/api/app/content/idp/validation.py", "Infosys Master Catalog", "29AABCI1234F1ZX", False),
    ("apps/api/app/content/idp/validation.py", "CloudScale Networks Master Catalog", "27AAPFU0939F1ZV", False),
    ("apps/api/app/content/idp/validation.py", "Bharti Airtel Master Catalog", "07AAACB0123L1Z4", False),
]

print("=== GSTIN VALIDATOR RUN ACROSS SEED SCRIPTS & CATALOGS ===\n")
print(f"{'Source File':<38} | {'Entity':<35} | {'GSTIN':<15} | {'Status':<6} | {'Details'}")
print("-" * 135)

for source, entity, gstin, is_intentional in gstin_inventory:
    is_valid, err = validate_gstin(gstin)
    expected_char = compute_gstin_check_char(gstin[:14])
    actual_char = gstin[14] if len(gstin) == 15 else "?"
    if is_intentional:
        status = "FAIL*"
        details = f"INTENTIONAL_INVALID: OCR digit confusion (Expected '{expected_char}', got '{actual_char}')"
    elif is_valid:
        status = "PASS"
        details = "Valid Base-36 Checksum"
    else:
        status = "FAIL"
        details = f"{err} (Expected '{expected_char}', got '{actual_char}')"
    print(f"{source:<38} | {entity:<35} | {gstin:<15} | {status:<6} | {details}")


