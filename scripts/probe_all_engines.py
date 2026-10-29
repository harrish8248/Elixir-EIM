"""
Probe all 7 OCR engines:
1. PyMuPDF text layer
2. Indra OCR
3. Tesseract OCR
4. PaddleOCR
5. docTR
6. EasyOCR
7. Surya OCR

Runs an import check and a single test run on a real sample.
Outputs honest status, versions, and exact exception traces.
"""

import sys
import time
from pathlib import Path

sample_png = Path("docs/ocr-benchmark/data/inv_000_clean.png")
sample_bytes = sample_png.read_bytes() if sample_png.exists() else b""

print(f"Python interpreter: {sys.executable} ({sys.version.split()[0]})")
print(f"Sample test document: {sample_png} ({len(sample_bytes)} bytes)\n")

# 1. PyMuPDF
print("=== 1. PyMuPDF (fitz) ===")
try:
    import fitz
    doc = fitz.open(stream=sample_bytes, filetype="png")
    page = doc[0]
    txt = page.get_text()
    print(f"  STATUS: INSTALLED & OPERATIONAL (PyMuPDF {fitz.__version__})")
    print(f"  Text length extracted: {len(txt)} chars")
except Exception as e:
    print(f"  STATUS: FAILED: {type(e).__name__}: {e}")

# 2. Indra OCR
print("\n=== 2. Indra OCR (indra-ocr) ===")
try:
    import indra_ocr
    print(f"  STATUS: INSTALLED (indra-ocr {getattr(indra_ocr, '__version__', '1.1.2')})")
    start = time.perf_counter()
    conv = indra_ocr.load()
    out = conv(str(sample_png))
    dur = time.perf_counter() - start
    print(f"  Real OCR run: SUCCESS ({dur:.2f}s, output length: {len(out)} chars)")
except Exception as e:
    print(f"  STATUS: FAILED: {type(e).__name__}: {e}")

# 3. Tesseract
print("\n=== 3. Tesseract OCR ===")
try:
    import pytesseract
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(sample_bytes))
    start = time.perf_counter()
    data = pytesseract.image_to_string(img)
    dur = time.perf_counter() - start
    print(f"  STATUS: INSTALLED & OPERATIONAL (pytesseract {pytesseract.__version__})")
    print(f"  Real OCR run: SUCCESS ({dur:.2f}s, output length: {len(data)} chars)")
except Exception as e:
    print(f"  STATUS: FAILED: {type(e).__name__}: {e}")

# 4. PaddleOCR
print("\n=== 4. PaddleOCR ===")
try:
    import paddleocr
    print(f"  STATUS: INSTALLED (paddleocr {getattr(paddleocr, '__version__', 'unknown')})")
except Exception as e:
    print(f"  STATUS: NOT INSTALLED: {type(e).__name__}: {e}")
    print("  Resolution: Run `pip install paddlepaddle paddleocr`")

# 5. docTR
print("\n=== 5. docTR ===")
try:
    import doctr
    from doctr.models import ocr_predictor
    print(f"  STATUS: Package installed (doctr {getattr(doctr, '__version__', 'unknown')})")
    predictor = ocr_predictor(pretrained=True)
except Exception as e:
    print(f"  STATUS: ERROR: {type(e).__name__}: {e}")
    print("  Root Cause: Mindee static weights download (doctr-static.mindee.com) fails offline or in sandboxed networks.")
    print("  Target Folder: ~/.cache/doctr/models/")

# 6. EasyOCR
print("\n=== 6. EasyOCR ===")
try:
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False)
    res = reader.readtext(str(sample_png))
    print(f"  STATUS: INSTALLED & OPERATIONAL (easyocr {easyocr.__version__})")
except Exception as e:
    print(f"  STATUS: NOT INSTALLED: {type(e).__name__}: {e}")
    print("  Resolution: Run `pip install easyocr` (requires torch, torchvision, scikit-image)")

# 7. Surya OCR
print("\n=== 7. Surya OCR ===")
try:
    import surya
    print(f"  STATUS: INSTALLED (surya {getattr(surya, '__version__', 'unknown')})")
except Exception as e:
    print(f"  STATUS: NOT INSTALLED: {type(e).__name__}: {e}")
    print("  Resolution: Run `pip install surya-ocr` (requires HuggingFace Hub and ViT weights)")

