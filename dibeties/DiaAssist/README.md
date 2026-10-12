# DiaAssist AI — React + FastAPI

Diabetes assistant: lab-report analysis, guideline-based AI answers (agentic RAG, offline with Ollama),
and a doctor-appointment system for patients and doctors.

```
backend/   FastAPI + SQLite + RAG pipeline (Python)
frontend/  React (Vite) user interface
```

## 1. One-time setup (Windows, PowerShell)

Requirements: Python 3.13, Node.js 20+, [Ollama](https://ollama.com).

```powershell
# --- backend ---
cd backend
py -3.13 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
ollama pull llama3.1:8b          # one-time download (~5 GB)
# optional OCR for photographed reports: install Tesseract, then set TESSERACT_CMD in .env
```

Put the real guideline documents (ADA Standards of Care, WHO fact sheets, PDF/TXT/DOCX) into
`backend/data/knowledge_base_docs/`, then train the knowledge base:

```powershell
python ingest.py
```

## 2. Run (two terminals)

```powershell
# terminal 1 — backend (http://localhost:8000, API docs at /docs)
cd backend ; venv\Scripts\activate
uvicorn api.main:app --port 8000

# terminal 2 — frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The database (`backend/data/diaassist.db`) is created and seeded on first start.

| Role    | Login                                   | Password     |
|---------|-----------------------------------------|--------------|
| Patient | patient@diaassist.ai                    | patient123   |
| Doctor  | sana.malik@diaassist.ai (and 5 others)  | doctor123    |
| Admin   | admin@diaassist.ai (link under login)   | admin123 (or `ADMIN_PASSWORD`) |

Doctors and the demo patient are **demonstration data**. Online payment is a **simulation** (no real money moves).
Newly registered doctors must be approved by the admin before they can log in.

## 3. Features

* **Login page opens first** (intro + sign in / sign up); "Continue as guest" opens Home, Doctors, Blogs and Contact without an account

* Separate patient / doctor sign-up and login, admin role; personal dashboard and history
* Doctor list with categories, qualification, fees, locations; filters
* Booking: date → slot → cash or (demo) online payment → automatic **token number** (per doctor per day)
* Cancel, reschedule (clinic follows the doctor's schedule for the new day), emergency postpone, delete history record
* Doctor dashboard: weekly calendar (free / booked), cancel a whole day (all patients notified), change location for a day, profile editing
* Doctors with several clinic locations (City Hospital, Care Clinic, Home Visit)
* In-app notifications (bell) for both sides; patient ↔ doctor messaging (after a shared appointment)
* Report analysis (PDF / photo with OCR / text) → value cards with range bars → **Consult a doctor** (suggests a speciality) → the report summary can be **shared with the doctor when booking**; the doctor sees it under *Patients → View report*
* AI assistant with conversation history, search, follow-up memory, source citations, verification, 👍/👎 feedback
* Admin: doctor approvals, knowledge-base upload and training, user control, feedback and contact messages
* Patient booking **calendar** (free / full / off / cancelled days), doctor **visit notes** shown to the patient, profile and password change for every role
* Admin can write, edit and delete blog articles
* Blogs, Contact us

## 4. Dataset preparation and model evaluation (for the viva)

```powershell
cd backend
python dataset_report.py                      # inventory -> cleaning -> chunking -> processed dataset + labelled lab reports
python ingest.py                              # "training": embeds chunks and builds the FAISS index
python evaluation/retrieval_eval.py           # baseline (TF-IDF) vs trained (dense embeddings), chunk-size comparison
python evaluation/extraction_eval.py          # report-extraction accuracy on 40 labelled synthetic reports
python evaluation/evaluate.py                 # full answers: agentic RAG vs plain RAG (slow — runs the LLM; leave it running)
python -m unittest discover -s tests -v       # 32 service-layer tests (accounts, booking, double-booking, cancel, reports, notes, ...)
cd ..\frontend ; npm test                    # frontend helper tests (range bars, tones, suggestions)
```

Honest notes for the report:
* Retrieval scores depend on the documents. With only the 2 placeholder files almost every chunk is returned, so numbers are inflated — add the real ADA/WHO documents first.
* The lab-report set is synthetic (generated with known answers), so 100 % extraction means "handles these layouts", not "works on every lab in the world".
* The language model is a pre-trained model (Llama 3.1 8B); the project's own "training" is the document pipeline (cleaning → chunking → embeddings → index), the rule-based report analyser and the evaluation, not fine-tuning the LLM.

## 5. Configuration

The demo-account hint on the login page is shown only in development (`npm run dev`); in a production build set `VITE_SHOW_DEMO=true` to show it.
Photo (PNG/JPG) reports need the Tesseract program; the Report page tells the user when it is missing. The backend warms up the model at start (`DIAASSIST_WARMUP=0` turns this off).

Edit `backend/.env` (LLM backend, model, chunk size, `MIN_RELEVANCE`, `CORS_ORIGINS`, `DIAASSIST_SECRET`, `ADMIN_PASSWORD`).
Decision support only — not a substitute for a qualified healthcare professional.
