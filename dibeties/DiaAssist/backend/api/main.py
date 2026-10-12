"""DiaAssist web API (FastAPI).

Run from the backend folder:   uvicorn api.main:app --reload --port 8000
Interactive documentation:     http://localhost:8000/docs
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import config  # noqa: E402
from api import seed, services  # noqa: E402
from api.services import ServiceError  # noqa: E402

app = FastAPI(title="DiaAssist API", version="1.0")

ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup() -> None:
    seed.seed_all()
    if os.getenv("DIAASSIST_WARMUP", "1") != "0":
        threading.Thread(target=_warm_up, daemon=True).start()


def _warm_up() -> None:
    """Loads the knowledge base and wakes the language model so the first real question is not slow."""
    try:
        get_pipeline()
    except Exception:  # noqa: BLE001 - not trained yet or model missing: reported by /api/health
        pass
    try:
        from src import llm_client
        llm_client.generate("Reply with the single word OK.", temperature=0.0, max_retries=1)
    except Exception:  # noqa: BLE001
        pass


@app.exception_handler(ServiceError)
async def _service_error(_request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


# ----------------------------------------------------------------------------- auth helpers
def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = services.user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in again.")
    return user


def require(*roles: str):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="You do not have access to this page.")
        return user
    return dependency


# ----------------------------------------------------------------------------- request models
class PatientSignup(BaseModel):
    email: str
    name: str
    password: str
    diabetes_type: str = ""


class DoctorSignup(BaseModel):
    email: str
    name: str
    password: str
    category: str
    qualification: str
    fee: int = Field(ge=0)
    experience_years: int = Field(default=0, ge=0)
    bio: str = ""


class LoginIn(BaseModel):
    email: str
    password: str
    role: str | None = None


class BookIn(BaseModel):
    doctor_id: int
    date: str
    time: str
    reason: str = ""
    payment_method: str = "cash"
    report: dict | None = None


class RescheduleIn(BaseModel):
    date: str
    time: str
    emergency: bool = False


class ReasonIn(BaseModel):
    reason: str = ""


class DayIn(BaseModel):
    date: str
    reason: str = "Emergency"


class LocationIn(BaseModel):
    date: str
    clinic_id: int


class ProfileIn(BaseModel):
    qualification: str | None = None
    fee: int | None = None
    bio: str | None = None
    experience_years: int | None = None


class ScheduleIn(BaseModel):
    weekday: int
    clinic_id: int
    start_time: str
    end_time: str
    slot_minutes: int = 30


class NotesIn(BaseModel):
    notes: str


class BlogIn(BaseModel):
    title: str
    category: str = ""
    summary: str = ""
    body: str


class ProfileUpdateIn(BaseModel):
    name: str | None = None
    diabetes_type: str | None = None


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


class MessageIn(BaseModel):
    body: str


class ContactIn(BaseModel):
    name: str
    email: str
    message: str


class ApprovalIn(BaseModel):
    approved: bool


class ActiveIn(BaseModel):
    active: bool


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None
    mode: str = "fast"
    report_text: str | None = None


class FeedbackIn(BaseModel):
    value: int | None


# ----------------------------------------------------------------------------- auth
@app.post("/api/auth/register/patient")
def register_patient(body: PatientSignup):
    services.register_patient(body.email, body.name, body.password, body.diabetes_type)
    return services.login(body.email, body.password, role="patient")


@app.post("/api/auth/register/doctor")
def register_doctor(body: DoctorSignup):
    services.register_doctor(body.email, body.name, body.password, body.category, body.qualification,
                             body.fee, body.experience_years, body.bio)
    return {"message": "Registration received. An administrator must approve your account before you can log in."}


@app.post("/api/auth/login")
def login(body: LoginIn):
    return services.login(body.email, body.password, body.role)


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return user


@app.put("/api/auth/profile")
def update_profile(body: ProfileUpdateIn, user: dict = Depends(current_user)):
    return services.update_profile(user["id"], body.name, body.diabetes_type)


@app.post("/api/auth/password")
def change_password(body: PasswordIn, user: dict = Depends(current_user)):
    services.change_password(user["id"], body.old_password, body.new_password)
    return {"ok": True}


# ----------------------------------------------------------------------------- public pages
@app.get("/api/health")
def health():
    from src import llm_client, vectorstore
    llm = llm_client.check_connection()
    status = vectorstore.get_training_status()
    from src import documents
    return {"api": "ok", "llm": llm, "ocr": documents.ocr_available(), "knowledge_base": {
        "trained": status["index_exists"], "documents": len(status["documents"]),
        "chunks": status["n_chunks"], "pending": status["pending"]}}


@app.get("/api/categories")
def categories():
    return services.CATEGORIES


@app.get("/api/clinics")
def clinics():
    return services.list_clinics()


@app.get("/api/doctors")
def doctors(category: str = "", q: str = "", max_fee: int | None = None, clinic: str = ""):
    return services.list_doctors(category, q, max_fee, clinic)


@app.get("/api/doctors/{doctor_id}")
def doctor(doctor_id: int):
    return services.get_doctor(doctor_id)


@app.get("/api/doctors/{doctor_id}/availability")
def availability(doctor_id: int, start: str = "", days: int = 35):
    return services.doctor_availability(doctor_id, start, days)


@app.get("/api/doctors/{doctor_id}/slots")
def slots(doctor_id: int, date: str):
    return services.get_slots(doctor_id, date)


@app.get("/api/blogs")
def blogs():
    return services.list_blogs()


@app.get("/api/blogs/{blog_id}")
def blog(blog_id: int):
    return services.get_blog(blog_id)


@app.post("/api/contact")
def contact(body: ContactIn):
    services.submit_contact(body.name, body.email, body.message)
    return {"message": "Thank you. We received your message."}


# ----------------------------------------------------------------------------- appointments
@app.post("/api/appointments")
def book(body: BookIn, user: dict = Depends(require("patient"))):
    return services.book_appointment(user["id"], body.doctor_id, body.date, body.time, body.reason, body.payment_method,
                                     body.report)


@app.get("/api/appointments")
def my_appointments(state: str = "", user: dict = Depends(require("patient", "doctor", "admin"))):
    return services.list_appointments(user, state)


@app.post("/api/appointments/{appointment_id}/cancel")
def cancel(appointment_id: int, body: ReasonIn, user: dict = Depends(require("patient", "doctor"))):
    return services.cancel_appointment(appointment_id, user, body.reason)


@app.post("/api/appointments/{appointment_id}/reschedule")
def reschedule(appointment_id: int, body: RescheduleIn, user: dict = Depends(require("patient"))):
    return services.reschedule_appointment(appointment_id, user, body.date, body.time, body.emergency)


@app.delete("/api/appointments/{appointment_id}")
def delete_appointment(appointment_id: int, user: dict = Depends(require("patient"))):
    services.delete_appointment(appointment_id, user)
    return {"deleted": appointment_id}


# ----------------------------------------------------------------------------- doctor tools
@app.get("/api/doctor/week")
def doctor_week(start: str = "", user: dict = Depends(require("doctor"))):
    return services.doctor_week(user["doctor_id"], start)


@app.post("/api/doctor/cancel-day")
def doctor_cancel_day(body: DayIn, user: dict = Depends(require("doctor"))):
    return services.doctor_cancel_day(user["doctor_id"], body.date, body.reason)


@app.post("/api/doctor/reopen-day")
def doctor_reopen_day(body: DayIn, user: dict = Depends(require("doctor"))):
    services.doctor_reopen_day(user["doctor_id"], body.date)
    return {"reopened": body.date}


@app.post("/api/doctor/location")
def doctor_location(body: LocationIn, user: dict = Depends(require("doctor"))):
    return services.doctor_set_location(user["doctor_id"], body.date, body.clinic_id)


@app.put("/api/doctor/profile")
def doctor_profile(body: ProfileIn, user: dict = Depends(require("doctor"))):
    return services.update_doctor_profile(user["doctor_id"], body.qualification, body.fee, body.bio, body.experience_years)


@app.put("/api/doctor/schedule")
def doctor_schedule(body: ScheduleIn, user: dict = Depends(require("doctor"))):
    services.set_schedule(user["doctor_id"], body.weekday, body.clinic_id, body.start_time, body.end_time, body.slot_minutes)
    return {"saved": True}


# ----------------------------------------------------------------------------- notifications and messages
@app.get("/api/notifications")
def notifications(user: dict = Depends(current_user)):
    return services.list_notifications(user["id"])


@app.post("/api/notifications/read")
def notifications_read(user: dict = Depends(current_user)):
    services.mark_notifications_read(user["id"])
    return {"ok": True}


@app.get("/api/messages/conversations")
def message_conversations(user: dict = Depends(require("patient", "doctor"))):
    return services.list_conversations(user)


@app.get("/api/messages/{other_id}")
def message_thread(other_id: int, after: int = 0, user: dict = Depends(require("patient", "doctor"))):
    return services.message_thread(user, other_id, after)


@app.post("/api/messages/{other_id}")
def send_message(other_id: int, body: MessageIn, user: dict = Depends(require("patient", "doctor"))):
    return services.send_message(user, other_id, body.body)


# ----------------------------------------------------------------------------- admin
@app.get("/api/admin/overview")
def admin_overview(_user: dict = Depends(require("admin"))):
    from src import vectorstore
    status = vectorstore.get_training_status()
    return {**services.admin_overview(), **services.feedback_stats(),
            "kb_documents": len(status["documents"]), "kb_chunks": status["n_chunks"], "kb_pending": status["pending"]}


@app.get("/api/admin/users")
def admin_users(_user: dict = Depends(require("admin"))):
    return services.admin_list_users()


@app.post("/api/admin/doctors/{doctor_id}/approval")
def admin_approval(doctor_id: int, body: ApprovalIn, _user: dict = Depends(require("admin"))):
    return services.admin_set_doctor_approval(doctor_id, body.approved)


@app.post("/api/admin/users/{user_id}/active")
def admin_active(user_id: int, body: ActiveIn, user: dict = Depends(require("admin"))):
    services.admin_set_user_active(user_id, body.active, user["id"])
    return {"ok": True}


@app.post("/api/appointments/{appointment_id}/notes")
def visit_notes(appointment_id: int, body: NotesIn, user: dict = Depends(require("doctor"))):
    return services.add_visit_notes(user, appointment_id, body.notes)


@app.post("/api/admin/blogs")
def admin_blog_create(body: BlogIn, _user: dict = Depends(require("admin"))):
    return services.create_blog(body.title, body.category, body.summary, body.body)


@app.put("/api/admin/blogs/{blog_id}")
def admin_blog_update(blog_id: int, body: BlogIn, _user: dict = Depends(require("admin"))):
    return services.update_blog(blog_id, body.title, body.category, body.summary, body.body)


@app.delete("/api/admin/blogs/{blog_id}")
def admin_blog_delete(blog_id: int, _user: dict = Depends(require("admin"))):
    services.delete_blog(blog_id)
    return {"deleted": blog_id}


@app.get("/api/admin/contact")
def admin_contact(_user: dict = Depends(require("admin"))):
    return services.list_contact_messages()


@app.get("/api/kb/status")
def kb_status(_user: dict = Depends(require("admin", "doctor"))):
    from src import vectorstore
    return vectorstore.get_training_status()


@app.post("/api/kb/upload")
async def kb_upload(file: UploadFile = File(...), _user: dict = Depends(require("admin"))):
    from src import vectorstore
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is too large (30 MB maximum).")
    try:
        name, outcome = vectorstore.add_document_bytes(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": name, "outcome": outcome, "note": "Press Train to include it in the assistant's knowledge."}


@app.post("/api/kb/train")
def kb_train(full: bool = False, _user: dict = Depends(require("admin"))):
    from src import vectorstore
    try:
        summary = vectorstore.train(force_full=full)
    except vectorstore.TrainingBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Training failed: {exc}") from exc
    _reset_pipeline()
    return summary


@app.get("/api/admin/feedback")
def admin_feedback(_user: dict = Depends(require("admin"))):
    return services.feedback_stats()


# ----------------------------------------------------------------------------- AI assistant
_pipeline = None
_pipeline_token = None
_pipeline_lock = threading.Lock()


def _reset_pipeline() -> None:
    global _pipeline, _pipeline_token
    with _pipeline_lock:
        _pipeline, _pipeline_token = None, None


def get_pipeline():
    """The trained pipeline; reloaded automatically after a new training run."""
    global _pipeline, _pipeline_token
    from src import vectorstore
    from src.orchestrator import AgenticRAGPipeline
    token = vectorstore.index_token()
    if token is None:
        raise HTTPException(status_code=409, detail="The knowledge base has not been trained yet. "
                                                    "An administrator must add documents and press Train, or run python ingest.py.")
    with _pipeline_lock:
        if _pipeline is None or _pipeline_token != token:
            try:
                _pipeline = AgenticRAGPipeline()
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=503, detail=f"Could not load the knowledge base: {exc}") from exc
            _pipeline_token = token
        return _pipeline


@app.post("/api/chat")
def chat(body: ChatIn, user: dict = Depends(current_user)):
    from src import llm_client
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Please type a question.")
    if len(message) > 2000:
        raise HTTPException(status_code=400, detail="The question is too long (2000 characters maximum).")
    if body.mode not in ("fast", "full"):
        raise HTTPException(status_code=400, detail="mode must be 'fast' or 'full'.")

    history = []
    if body.conversation_id:
        history = [{"role": m["role"], "content": m["content"]}
                   for m in services.chat_messages(body.conversation_id, user["id"])][-6:]
    pipeline = get_pipeline()
    try:
        result = pipeline.run(message, report_text=body.report_text, mode=body.mode, history=history)
    except llm_client.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conv_id = body.conversation_id or services.create_conversation(user["id"], message)
    services.add_chat_message(conv_id, user["id"], "user", message)
    sources = [{"source": c["source"], "score": round(c.get("score", 0.0), 3), "content": c["content"][:400]}
               for c in result["retrieved_chunks"]]
    answer_id = services.add_chat_message(conv_id, user["id"], "assistant", result["response"],
                                          [s["source"] for s in sources], result["mode"],
                                          result["response_time_sec"], result["verified"])
    return {"conversation_id": conv_id, "message_id": answer_id, "response": result["response"], "sources": sources,
            "verified": result["verified"], "verification_status": result["verification_status"],
            "issues": result["verification_issues"], "mode": result["mode"], "seconds": result["response_time_sec"],
            "report_interpretation": result["report_interpretation"], "no_information": result.get("no_information", False)}


@app.get("/api/chat/conversations")
def chat_conversations(q: str = "", user: dict = Depends(current_user)):
    return services.list_conversations_chat(user["id"], q)


@app.get("/api/chat/conversations/{conversation_id}")
def chat_conversation(conversation_id: int, user: dict = Depends(current_user)):
    return services.chat_messages(conversation_id, user["id"])


@app.delete("/api/chat/conversations/{conversation_id}")
def chat_delete(conversation_id: int, user: dict = Depends(current_user)):
    services.delete_conversation(conversation_id, user["id"])
    return {"deleted": conversation_id}


@app.post("/api/chat/messages/{message_id}/feedback")
def chat_feedback(message_id: int, body: FeedbackIn, user: dict = Depends(current_user)):
    services.set_chat_feedback(message_id, user["id"], body.value)
    return {"ok": True}


@app.post("/api/report/analyze")
async def analyze_report(file: UploadFile | None = File(default=None), text: str = Form(default=""),
                         _user: dict = Depends(current_user)):
    """Upload a report (PDF, photo, TXT, DOCX) or send its text. Returns the classified values."""
    from src import documents
    from src.agents import report_analysis
    report_text = text or ""
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File is too large (15 MB maximum).")
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in documents.REPORT_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Please upload a PDF, PNG, JPG, TXT or DOCX file.")
        try:
            report_text = documents.extract_text(file.filename, data, page_markers=False, ocr=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not report_text.strip():
        raise HTTPException(status_code=422, detail="No text could be read from this report.")
    if len(report_text) > 60000:
        raise HTTPException(status_code=413, detail="The report text is too long.")
    result = report_analysis.analyze_report_detailed(report_text)
    return {"text": report_text, **result}
