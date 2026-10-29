"""
Diagnose CER Root Cause on Single Clean Invoice Page.
Performs character-level alignment and diff between Ground Truth and OCR Output.
"""

import difflib
import json
from pathlib import Path
from PIL import Image
import pytesseract

def main():
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    # Check data/clean_inv_001.png and data/clean_inv_001.json
    img_path = Path("docs/ocr-benchmark/data/inv_000_clean.png")
    gt_path = Path("docs/ocr-benchmark/data/inv_000_clean.json")
    
    if not img_path.exists():
        print(f"File not found: {img_path}")
        return

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    img = Image.open(img_path)
    ocr_text = pytesseract.image_to_string(img, config="--psm 3")

    # How was gt_text constructed in evaluation.py vs ocr_text?
    # Let's inspect gt_data keys
    print("GT Data Keys:", list(gt_data.keys()))
    gt_raw = gt_data.get("full_text") or gt_data.get("raw_text") or ""
    print(f"GT Text length: {len(gt_raw)} chars")
    print(f"OCR Text length: {len(ocr_text)} chars")

    # Character-level Levenshtein distance
    # Standard CER = Levenshtein(gt, ocr) / max(len(gt), 1)
    matcher = difflib.SequenceMatcher(None, gt_raw, ocr_text)
    opcodes = matcher.get_opcodes()
    
    # Calculate edits
    insertions = 0
    deletions = 0
    substitutions = 0
    matches = 0
    
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'equal':
            matches += (i2 - i1)
        elif tag == 'replace':
            substitutions += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            deletions += (i2 - i1)
        elif tag == 'insert':
            insertions += (j2 - j1)

    total_edits = substitutions + deletions + insertions
    cer = total_edits / max(len(gt_raw), 1)
    print(f"\n--- CER DIAGNOSTICS FOR clean_inv_001.png ---")
    print(f"Matches: {matches}")
    print(f"Substitutions: {substitutions}")
    print(f"Deletions: {deletions}")
    print(f"Insertions: {insertions}")
    print(f"Total Edits: {total_edits}")
    print(f"CER: {cer * 100:.2f}%\n")

    print("--- FIRST 15 DIFF OPERATIONS (SIDE BY SIDE) ---")
    for tag, i1, i2, j1, j2 in opcodes[:15]:
        gt_chunk = repr(gt_raw[i1:i2])
        ocr_chunk = repr(ocr_text[j1:j2])
        print(f"{tag.upper():7s} | GT [{i1}:{i2}]: {gt_chunk[:40]:42s} | OCR [{j1}:{j2}]: {ocr_chunk[:40]}")

    print("\n--- SAMPLE GT vs OCR BLOCK ---")
    print("GT First 300 chars:")
    print(repr(gt_raw[:300]))
    print("OCR First 300 chars:")
    print(repr(ocr_text[:300]))

if __name__ == "__main__":
    main()
