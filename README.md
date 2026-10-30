# Elixir EIM

**A secure place for a company's documents: store them, find them, approve them, read invoices automatically, and prove who did what.**

Elixir EIM (Enterprise Information Management) is a web application for organizations that must control and prove how they handle documents, such as banks, hospitals, law firms and finance teams. It also reads invoices with free, open-source OCR, with special support for Indian GST invoices.

> **Project status: work in progress.** The secure foundation and the invoice-capture pipeline work and are tested. Some modules are still partial. See [What works today](#what-works-today).

---

## What can I do with it?

| I want to... | Where to go in the app | What happens |
|---|---|---|
| Store and organize documents | **Content Services** | Upload files into workspaces and folders. Every upload is checked for viruses first. |
| Turn a scanned invoice into data | **Capture & IDP** | OCR reads the invoice and fills in the invoice number, date, GSTINs, taxes and total. |
| Check and correct what OCR read | **Capture & IDP > Review** | See the document next to the extracted fields, click a field to highlight where it came from, fix mistakes. |
| Choose which OCR engines run | **OCR Engines** | Switch engines on or off and see which ones are installed and healthy. |
| Find a document | **Search & Discovery** | Search by name, text inside scans, invoice number or GSTIN. You only see what you are allowed to see. |
| Keep records for the legal period | **Records & Retention** | Set retention schedules and place legal holds that block deletion. |
| Get documents approved | **Process Automation** | Send approval tasks to another person. Nobody can approve their own work. |
| Prove nothing was changed | **Policy & Guardrails / Audit** | Every action is written to a log where each entry is linked to the previous one. Click *Verify* to check the chain. |

---

## How it keeps data safe (in plain words)

1. **Every request is checked.** Before anything happens, a policy engine (Open Policy Agent) decides yes or no based on who you are, your department and your clearance level. If the engine is unreachable, the answer is no.
2. **Companies are separated at the database level.** Each customer's rows are tagged and the database itself refuses to show one customer's data to another.
3. **Files are scanned.** ClamAV checks uploads before they are processed.
4. **Everything is logged.** The audit log is append-only and hash-chained, so any change to history is detectable ("tamper-evident").
5. **Nothing leaves your machine.** OCR runs locally. No document is sent to an outside service, and document text is kept out of the logs.

---

## How invoice reading works

```
Upload -> Virus scan -> OCR -> Classify -> Extract fields -> Validate -> Human review -> File + make searchable
```

- **OCR engines:** Tesseract (English plus Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati and Punjabi), Indra OCR (fast, CPU-only) and the PDF text layer. Other engines are used automatically if you install them.
- **GSTIN checking:** each GSTIN is checked for format and its built-in check character. If OCR confuses characters like `O` and `0`, the system tries fixes and keeps only one that passes the check.
- **Tax checks:** taxable value + CGST + SGST (or IGST) must equal the total. Duplicate invoices are flagged.
- **e-Invoice QR codes** are decoded offline and used to cross-check the OCR result.
- **Positions:** every extracted field remembers where it was on the page, so the review screen can highlight it.
- **Not sure? A person decides.** Invoices that fail a check go to a review queue instead of being approved automatically.

**Indra OCR note:** it supports Latin, Cyrillic, Greek, Devanagari, Bengali and Chinese. It does **not** read Tamil, Telugu, Kannada or Malayalam. Tesseract handles those.

---

## Get started

### What you need
- Windows 10/11 with **Docker** (WSL2 backend)
- **Python 3.13**
- **Node.js 20+**
- **Tesseract 5**: `winget install UB-Mannheim.TesseractOCR`
- About 6 GB of free disk space and 8 GB of RAM (more is better)

### Install and run
```powershell
git clone https://github.com/harrish8248/Elixir-EIM.git
cd Elixir-EIM

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock

npm --prefix apps/web install

.\start.ps1 -Demo
```

`start.ps1 -Demo` starts the services, prepares the database, loads demo data and prints a pass/fail table. The first start can take a few minutes because Keycloak and ClamAV are slow to warm up.

| What | Address |
|---|---|
| Web app | http://localhost:5173 |
| API documentation | http://127.0.0.1:8000/docs |

**Demo logins** are listed in [docs/DEMO.md](docs/DEMO.md). Start with the Records Manager account to see everything, then try an HR user to see how permissions hide Finance documents.

To wipe the demo data and start fresh: `.\start.ps1 -ResetDemo`

---

## Your first 5 minutes

1. **Sign in** with a demo account.
2. Open **Capture & IDP** and click **Upload Document**. Choose an invoice image from `docs/demo-samples/`.
3. Watch the status move from scanning to processing to *needs review* or *approved*.
4. Click **Review**. Click the GSTIN field and see it highlighted on the invoice. Correct any field and save.
5. Open **Search & Discovery** and search for the invoice number or part of the GSTIN.
6. Sign out, sign in as a user from another department, and repeat the search. The invoice should not appear.
7. Open **Policy & Guardrails** and click the audit verification button to check the log.

---

## What works today

| Area | State |
|---|---|
| Login, permissions, company separation, audit log | Built and tested |
| Content, records, approvals, search | Built; more browser-level testing planned |
| OCR and GST invoice capture | Working; date and total extraction still improving |
| OCR Engines page and hardware-aware engine choice | In progress |
| Workflow designer, automatic retention jobs, integrations, AI assistant, analytics | Not built yet |
| Automated checks on GitHub (CI) | Written, not yet run |

### How accurate is the OCR?
On a set of 110 synthetic test invoices that the system was never tuned on, **plain OCR without the QR code** read the supplier GSTIN correctly **98%** of the time and the invoice number **98%**. Invoice date (31%), total (48%) and taxable value (47%) are **weak and being improved**. These are test results on generated invoices; accuracy on real invoices has not been measured yet. Method and tables: [docs/OCR_ACCURACY.md](docs/OCR_ACCURACY.md).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Services stop or ports stop responding after a while | WSL shuts down when idle. Keep it alive: `Start-Process wsl -ArgumentList "-d","Ubuntu","sleep","infinity" -WindowStyle Hidden`, then run `.\start.ps1 -Demo` again. |
| A page shows "API Error 404" | A stale backend is still running. Stop it, then restart with `.\start.ps1 -Demo`. |
| Login hangs or fails | Keycloak takes 1 to 2 minutes to start. Check `docker ps` until it shows healthy. |
| OCR says Tesseract is not found | Install Tesseract (see above) and make sure its install folder is configured in `.env`. |
| An OCR engine shows "Not installed" | That engine's model files could not be downloaded. The app still works with the engines that are installed. |
| Computer is slow | Close other apps. Gotenberg (document preview) is optional and can be left off. |

---

## Run the tests

```powershell
pytest apps/api/tests -v                                   # backend
lint-imports                                               # code boundaries
docker exec elixir-opa opa test /policies -v               # permission policies
npm --prefix apps/web test -- --run                        # frontend
python cli/elixir_admin/main.py ocr evaluate --split test  # OCR accuracy
```

---

## Technology

**Backend:** Python, FastAPI, SQLAlchemy, Alembic. **Frontend:** React, TypeScript, Tailwind CSS. **Data:** PostgreSQL 16 (row-level security), Redis, MinIO. **Security:** Keycloak (login), Open Policy Agent (permissions), ClamAV (virus scan). **OCR:** Tesseract, Indra OCR, PyMuPDF, OpenCV.

## Project layout

```
apps/api/     backend (identity, permissions, audit, content and invoice capture, records, workflow, search, admin)
apps/web/     web app
policies/     permission rules and their tests
migrations/   database changes
cli/          elixir-admin command-line tool
scripts/      demo data and benchmark tools
docs/         architecture, demo guide, OCR accuracy, licenses
```

## License

Apache-2.0. Third-party OCR engines and model weights have their own terms; see [docs/THIRD_PARTY_LICENSES.md](docs/THIRD_PARTY_LICENSES.md). Indra OCR's model weights carry use restrictions, so review them before any commercial use.
