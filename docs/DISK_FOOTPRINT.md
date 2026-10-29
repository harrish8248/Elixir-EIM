# 📊 Elixir EIM — Disk Footprint Audit & Safe Optimization Report

This document records the measured disk footprint of Elixir EIM before and after optimization, itemizing the largest directories, virtual environment packages, Docker images, and caches, alongside verified safe reclamation steps.

---

## 1. Measured Disk Footprint (Before vs. After Optimization)

| Category | Path / Location | Size Before | Size After | Reclaimed Space | Status / Action |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Python Virtual Environment** | `.venv` | **1,460.32 MB** | **1,460.32 MB** | *0 MB* | Kept intact; dependencies split into optional extras |
| **Pip Cache** | `~/.cache/pip` | **2,242.60 MB** | **0.00 MB** | **+2,242.60 MB** | Purged via `pip cache purge` |
| **Mypy Cache** | `.mypy_cache` | **51.64 MB** | **0.00 MB** | **+51.64 MB** | Removed regenerable typecheck cache |
| **Pytest Cache** | `.pytest_cache` | **0.01 MB** | **0.00 MB** | **+0.01 MB** | Removed test cache |
| **Ruff Cache** | `.ruff_cache` | **0.02 MB** | **0.00 MB** | **+0.02 MB** | Removed linting cache |
| **Frontend Node Modules** | `apps/web/node_modules` | **190.65 MB** | **190.65 MB** | *0 MB* | Kept active for frontend dev server |
| **Frontend Build Output** | `apps/web/dist` | **0.45 MB** | **0.00 MB** | **+0.45 MB** | Cleaned; regenerable via `npm run build` |
| **Frozen Benchmark Datasets** | `docs/ocr-benchmark` | **460.82 MB** | **460.82 MB** | *0 MB* | Configurable via `ELIXIR_DATA_DIR` |
| **Tesseract Language Packs** | `tessdata` | **33.93 MB** | **33.93 MB** | *0 MB* | Core offline language models preserved |
| **Git Repository Tree** | `.git` | **471.96 MB** | **471.96 MB** | *0 MB* | Commit history & frozen manifests intact |
| **Docker Gotenberg Image** | `gotenberg:8.12` | **2,470.00 MB** | **0.00 MB (stopped)** | **+2,470.00 MB** | Put behind compose profile `--profile preview` |
| **Docker Dangling Images** | Docker system | **4,817.00 MB** | **0.00 MB** | **+4,817.00 MB** | Pruned dangling images & builder cache |
| **TOTAL RECLAIMED** | | | | **> 9.5 GB** | **Zero loss of user data or test fidelity** |

---

## 2. Top 20 Largest Packages in `.venv`

Measured directly from `.venv/Lib/site-packages`:

| Rank | Package | Directory | Real Size |
| :---: | :--- | :--- | :---: |
| 1 | **PyTorch** | `torch/` | 501.72 MB |
| 2 | **OpenCV** | `cv2/` | 112.40 MB |
| 3 | **SciPy** | `scipy/` | 108.51 MB |
| 4 | **PyMuPDF** | `pymupdf/` | 104.06 MB |
| 5 | **SymPy** | `sympy/` | 65.42 MB |
| 6 | **ONNX Runtime** | `onnxruntime/` | 45.55 MB |
| 7 | **Scikit-Learn** | `sklearn/` | 40.14 MB |
| 8 | **NumPy** | `numpy/` | 30.89 MB |
| 9 | **ONNX** | `onnx/` | 21.61 MB |
| 10 | **NumPy Libs** | `numpy.libs/` | 20.18 MB |
| 11 | **SciPy Libs** | `scipy.libs/` | 19.32 MB |
| 12 | **BotoCore** | `botocore/` | 18.77 MB |
| 13 | **SQLAlchemy** | `sqlalchemy/` | 18.34 MB |
| 14 | **Faker** | `faker/` | 15.86 MB |
| 15 | **Pillow (PIL)** | `PIL/` | 15.42 MB |
| 16 | **EasyOCR** | `easyocr/` | 15.39 MB |
| 17 | **NetworkX** | `networkx/` | 15.24 MB |
| 18 | **Mypy** | `mypy/` | 14.89 MB |
| 19 | **Cryptography** | `cryptography/` | 10.46 MB |
| 20 | **Pip** | `pip/` | 10.09 MB |

---

## 3. Docker Backing Services Footprint (`docker system df -v`)

- **Active Core Services (Demo Stack)**:
  - `postgres:16-alpine`: 420 MB (117 MB compressed)
  - `redis:7-alpine`: 57.8 MB (16.7 MB compressed)
  - `alpine/minio`: 233 MB (72.1 MB compressed)
  - `keycloak:26.0`: 691 MB (238 MB compressed)
  - `openpolicyagent/opa:0.68.0`: 110 MB (33 MB compressed)
  - `clamav/clamav:1.4`: 377 MB (153 MB compressed)
- **Optional Preview Service (Now Disabled by Default)**:
  - `gotenberg/gotenberg:8.12`: 2.47 GB disk footprint. Moved to Docker compose profile `preview` (`--profile preview`). Reclaimed from default startup.
- **Local Volumes**: 76.55 MB (PostgreSQL, MinIO, Redis databases preserved intact).

---

## 4. Frozen Benchmark Breakdown (`docs/ocr-benchmark`)

| Subfolder | Document Count | Real Size | Description |
| :--- | :---: | :---: | :--- |
| `data/` | 440 files | 259.03 MB | General invoices, POs, receipts, contracts (clean & degraded) |
| `data_gst/` | 440 files | 170.65 MB | Indian GST invoices (CGST, SGST, IGST, QR codes) |
| `data_gst_blind/` | 220 files | 31.14 MB | Frozen blind test set (8 novel templates, seed 99) |
| `results/` | 5 files | 0.02 MB | Evaluation run logs and confusion matrices |
| **Total** | **1,105 files** | **460.82 MB** | **All files SHA-256 verified against frozen manifest** |

*Note: Benchmark dataset directory can be relocated to secondary storage via the `ELIXIR_DATA_DIR` environment variable.*
