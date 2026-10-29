# Third-Party OCR Engines & IDP Libraries License Inventory

Elixir EIM incorporates and interfaces with open-source optical character recognition (OCR) and intelligent document processing (IDP) libraries. All integrated components comply with enterprise open-source licensing standards.

| Component / Engine | License | Upstream Project / Repository | Role in Elixir EIM | Distribution & Usage Notes |
|---|---|---|---|---|
| **PyMuPDF (`fitz`)** | **AGPL-3.0** | Artifex Software / PyMuPDF | Digital PDF Text Layer Extraction | High-speed native vector stream parser; only accessed via service layer. |
| **Indra OCR** | **MIT** | DataLab TO (`datalab-to/indra-ocr`) | Indic / Multilingual Transformer OCR | ONNX layout analysis and text recognition for Hindi and complex enterprise layouts. |
| **Tesseract OCR (`pytesseract`)** | **Apache 2.0** | Ray Smith / Google / Tesseract-OCR | Primary Production OCR Engine | Default baseline engine with adaptive OpenCV preprocessing and multi-pass PSM. |
| **OpenCV (`opencv-python-headless`)** | **Apache 2.0** | OpenCV Team | Image Preprocessing Pipeline | Image deskew, CLAHE contrast enhancement, bilateral filtering, Hough line transforms. |
| **scikit-learn** | **BSD 3-Clause** | scikit-learn developers | Document Type Classifier | TF-IDF vectorization and Multinomial Logistic Regression for automated document classification. |
| **Pillow (`PIL`)** | **HPND** | Jeffrey A. Clark (Alex Clark) & Contributors | Image Manipulation | Canvas rendering, DPI scaling, and format conversion. |
| **PaddleOCR** | **Apache 2.0** | Baidu PaddlePaddle | Optional Secondary Neural Engine | Deep learning multilingual OCR with angle classification (optional plugin). |
| **docTR** | **Apache 2.0** | Mindee | Secondary Neural OCR Engine | DBNet text detection and CRNN recognition architecture (offline weights optional). |
| **EasyOCR** | **Apache 2.0** | JaidedAI | Optional Scene Text OCR Engine | CRAFT text detection and PyTorch recognition framework. |
| **Surya OCR** | **GPL-3.0** | Vik Paruchuri (`datalab-to/surya`) | Optional Layout & Reading Order Engine | Vision Transformer for document layout analysis and multilingual recognition. |
| **Ollama** | **MIT** | Ollama Team | Local Multimodal Vision Integration | Local offline HTTP API daemon for zero-shot visual document reasoning (LLaVA / MiniCPM). |

---

## License Compatibility & Isolation Guarantees

1. **Permissive MIT, Apache 2.0, and BSD-3 Libraries:**
   Tesseract, Indra OCR, OpenCV, docTR, PaddleOCR, and scikit-learn are licensed under standard permissive commercial licenses without copyleft restrictions.
2. **Copyleft & Network Separation (AGPL-3.0 & GPL-3.0):**
   - PyMuPDF (AGPL-3.0) and Surya (GPL-3.0) run strictly isolated within service boundary interfaces (`PyMuPdfEngine`, `SuryaEngine`). If a commercial deployment requires proprietary redistribution without source disclosure, the modular router allows toggling PyMuPDF to OFF in favor of pure Apache 2.0 Tesseract and MIT Indra OCR pipelines with zero downtime.
3. **No External Proprietary OCR APIs:**
   No document bytes or image data are ever transmitted to third-party cloud OCR APIs (Google Cloud Vision, AWS Textract, Azure Document Intelligence). All inference executes locally on-premise.
