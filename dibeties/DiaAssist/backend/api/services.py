"""Business logic for DiaAssist (no web framework here, so it can be unit-tested on its own).

Covers: accounts and roles, doctor profiles, schedules and free/busy slots, appointments
(book, cancel, reschedule, emergency postpone, delete, history), token numbers, simulated
payment, doctor emergency day-cancel and clinic location changes, notifications,
patient-doctor messages, blogs, contact messages and the admin approval flow.
"""
import json
import re
import sqlite3
from datetime import date as Date, datetime, timedelta

from api import db

CATEGORIES = ["Endocrinology", "Diabetes educator", "Nutrition", "Eye care", "Kidney care", "Foot care"]
DIABETES_TYPES = ["Type 1 diabetes", "Type 2 diabetes", "Gestational diabetes", "Pre-diabetes"]
MAX_DAYS_AHEAD = 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _row(r):
    return dict(r) if r is not None else None


def _check_date(value: str) -> Date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ServiceError("Date must look like 2026-10-15.") from None


def _check_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except (TypeError, ValueError):
        raise ServiceError("Time must look like 16:30.") from None


def _now() -> datetime:
    return datetime.now()


def notify(c, user_id: int, text: str) -> None:
    c.execute("INSERT INTO notifications(user_id,text,created_at) VALUES (?,?,?)", (user_id, text, db.now_iso()))


# ============================================================================ accounts
def _user_public(row) -> dict:
    d = dict(row)
    d.pop("password_hash", None)
    return d


def register_patient(email: str, name: str, password: str, diabetes_type: str = "") -> dict:
    email = (email or "").strip().lower()
    _validate_account(email, name, password)
    if diabetes_type and diabetes_type not in DIABETES_TYPES:
        raise ServiceError("Please choose a valid diabetes type.")
    return _create_user(email, name.strip(), password, "patient", diabetes_type)


def _validate_account(email: str, name: str, password: str) -> None:
    if not EMAIL_RE.match(email or ""):
        raise ServiceError("Please enter a valid email address.")
    if not (name or "").strip():
        raise ServiceError("Name is required.")
    if len(password or "") < 6:
        raise ServiceError("Password must be at least 6 characters.")


def _create_user(email, name, password, role, diabetes_type="") -> dict:
    try:
        with db.connect() as c:
            cur = c.execute(
                "INSERT INTO users(email,name,role,password_hash,diabetes_type,created_at) VALUES (?,?,?,?,?,?)",
                (email, name, role, db.hash_password(password), diabetes_type, db.now_iso()))
            return _user_public(c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError:
        raise ServiceError("An account with this email already exists.", 409) from None


def register_doctor(email: str, name: str, password: str, category: str, qualification: str,
                    fee: int, experience_years: int = 0, bio: str = "") -> dict:
    """Creates a doctor account that is NOT listed until an administrator approves it."""
    email = (email or "").strip().lower()
    _validate_account(email, name, password)
    if category not in CATEGORIES:
        raise ServiceError("Please choose a valid specialty.")
    if not (qualification or "").strip():
        raise ServiceError("Qualification is required.")
    try:
        fee = int(fee)
        experience_years = int(experience_years or 0)
    except (TypeError, ValueError):
        raise ServiceError("Fee and experience must be numbers.") from None
    if fee < 0 or experience_years < 0:
        raise ServiceError("Fee and experience cannot be negative.")
    user = _create_user(email, name.strip(), password, "doctor")
    with db.connect() as c:
        c.execute("INSERT INTO doctors(user_id,category,qualification,experience_years,fee,bio,approved) "
                  "VALUES (?,?,?,?,?,?,0)", (user["id"], category, qualification.strip(), experience_years, fee, bio))
        for admin in c.execute("SELECT id FROM users WHERE role='admin' AND active=1").fetchall():
            notify(c, admin["id"], f"New doctor registration waiting for approval: {name.strip()}")
    return user


def login(email: str, password: str, role: str | None = None) -> dict:
    """Returns {'token', 'user'}. If `role` is given the account must have that role
    (so the patient page cannot be used to sign in a doctor and vice versa)."""
    email = (email or "").strip().lower()
    with db.connect() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if row is None or not db.verify_password(password or "", row["password_hash"]):
        raise ServiceError("Invalid email or password.", 401)
    if not row["active"]:
        raise ServiceError("This account has been disabled.", 403)
    if role and row["role"] != role:
        raise ServiceError(f"This is not a {role} account. Use the {row['role']} login page.", 403)
    if row["role"] == "doctor":
        with db.connect() as c:
            d = c.execute("SELECT approved FROM doctors WHERE user_id=?", (row["id"],)).fetchone()
        if d is None or not d["approved"]:
            raise ServiceError("Your doctor account is waiting for administrator approval.", 403)
    return {"token": db.make_token(row["id"], row["role"]), "user": _user_public(row)}


def user_from_token(token: str) -> dict | None:
    data = db.read_token(token or "")
    if not data:
        return None
    with db.connect() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (data["uid"],)).fetchone()
    if row is None or not row["active"]:
        return None
    user = _user_public(row)
    if user["role"] == "doctor":
        with db.connect() as c:
            d = c.execute("SELECT id FROM doctors WHERE user_id=?", (user["id"],)).fetchone()
        user["doctor_id"] = d["id"] if d else None
    return user


# ============================================================================ doctors
_DOCTOR_SELECT = (
    "SELECT d.id, d.user_id, u.name, d.category, d.qualification, d.experience_years, d.fee, d.bio, "
    "d.approved, d.is_demo FROM doctors d JOIN users u ON u.id = d.user_id")


def _doctor_clinics(c, doctor_id: int) -> list:
    rows = c.execute(
        "SELECT cl.id, cl.name, s.weekday, s.start_time, s.end_time FROM schedule s "
        "JOIN clinics cl ON cl.id = s.clinic_id WHERE s.doctor_id=? ORDER BY s.weekday", (doctor_id,)).fetchall()
    return [dict(r) for r in rows]


def list_clinics() -> list:
    with db.connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clinics ORDER BY name")]


def list_doctors(category: str = "", q: str = "", max_fee: int | None = None, clinic: str = "") -> list:
    """Approved doctors only, with optional filters."""
    sql = _DOCTOR_SELECT + " WHERE d.approved=1 AND u.active=1"
    args = []
    if category:
        sql += " AND d.category=?"
        args.append(category)
    if q:
        sql += " AND (u.name LIKE ? OR d.qualification LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if max_fee is not None:
        sql += " AND d.fee<=?"
        args.append(int(max_fee))
    sql += " ORDER BY u.name"
    out = []
    with db.connect() as c:
        for r in c.execute(sql, args).fetchall():
            d = dict(r)
            d["clinics"] = _doctor_clinics(c, d["id"])
            if clinic and not any(cl["name"] == clinic for cl in d["clinics"]):
                continue
            d["next_free"] = _next_free(c, d["id"])
            out.append(d)
    return out


def get_doctor(doctor_id: int, include_unapproved: bool = False) -> dict:
    with db.connect() as c:
        r = c.execute(_DOCTOR_SELECT + " WHERE d.id=?", (doctor_id,)).fetchone()
        if r is None or (not r["approved"] and not include_unapproved):
            raise ServiceError("Doctor not found.", 404)
        d = dict(r)
        d["clinics"] = _doctor_clinics(c, doctor_id)
        d["next_free"] = _next_free(c, doctor_id)
        return d


def update_doctor_profile(doctor_id: int, qualification=None, fee=None, bio=None, experience_years=None) -> dict:
    fields, args = [], []
    for col, val in (("qualification", qualification), ("fee", fee), ("bio", bio), ("experience_years", experience_years)):
        if val is not None:
            if col in ("fee", "experience_years"):
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    raise ServiceError(f"{col} must be a number.") from None
                if val < 0:
                    raise ServiceError(f"{col} cannot be negative.")
            fields.append(f"{col}=?")
            args.append(val)
    if fields:
        with db.connect() as c:
            c.execute(f"UPDATE doctors SET {', '.join(fields)} WHERE id=?", (*args, doctor_id))
    return get_doctor(doctor_id, include_unapproved=True)


def set_schedule(doctor_id: int, weekday: int, clinic_id: int, start_time: str, end_time: str, slot_minutes: int = 30) -> None:
    start_time, end_time = _check_time(start_time), _check_time(end_time)
    if not 0 <= int(weekday) <= 6:
        raise ServiceError("Weekday must be 0 (Monday) to 6 (Sunday).")
    if start_time >= end_time:
        raise ServiceError("End time must be after start time.")
    if int(slot_minutes) not in (15, 20, 30, 45, 60):
        raise ServiceError("Slot length must be 15, 20, 30, 45 or 60 minutes.")
    with db.connect() as c:
        if c.execute("SELECT 1 FROM clinics WHERE id=?", (clinic_id,)).fetchone() is None:
            raise ServiceError("Clinic not found.", 404)
        c.execute(
            "INSERT INTO schedule(doctor_id,weekday,clinic_id,start_time,end_time,slot_minutes) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(doctor_id,weekday) DO UPDATE SET clinic_id=excluded.clinic_id, start_time=excluded.start_time, "
            "end_time=excluded.end_time, slot_minutes=excluded.slot_minutes",
            (doctor_id, int(weekday), clinic_id, start_time, end_time, int(slot_minutes)))


# ============================================================================ slots / calendar
def _day_info(c, doctor_id: int, day: Date):
    """(clinic_id, start, end, slot_minutes, cancelled, reason) for that date, or None if not working."""
    sch = c.execute("SELECT * FROM schedule WHERE doctor_id=? AND weekday=?", (doctor_id, day.weekday())).fetchone()
    ov = c.execute("SELECT * FROM day_overrides WHERE doctor_id=? AND date=?", (doctor_id, day.isoformat())).fetchone()
    if sch is None:
        return None
    clinic_id = ov["clinic_id"] if ov is not None and ov["clinic_id"] else sch["clinic_id"]
    cancelled = bool(ov["cancelled"]) if ov is not None else False
    reason = ov["reason"] if ov is not None else ""
    return clinic_id, sch["start_time"], sch["end_time"], sch["slot_minutes"], cancelled, reason


def _times(start: str, end: str, step: int) -> list:
    t = datetime.strptime(start, "%H:%M")
    stop = datetime.strptime(end, "%H:%M")
    out = []
    while t + timedelta(minutes=step) <= stop:
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=step)
    return out


def _slots(c, doctor_id: int, day: Date, exclude_appointment: int | None = None) -> dict:
    info = _day_info(c, doctor_id, day)
    if info is None:
        return {"working": False, "cancelled": False, "clinic": None, "slots": []}
    clinic_id, start, end, step, cancelled, reason = info
    clinic = _row(c.execute("SELECT id, name FROM clinics WHERE id=?", (clinic_id,)).fetchone())
    booked = {r["time"]: r for r in c.execute(
        "SELECT a.time, a.token, a.id, u.name AS patient FROM appointments a JOIN users u ON u.id=a.patient_id "
        "WHERE a.doctor_id=? AND a.date=? AND a.status='confirmed'", (doctor_id, day.isoformat())).fetchall()}
    now = _now()
    slots = []
    for t in _times(start, end, step):
        past = datetime.combine(day, datetime.strptime(t, "%H:%M").time()) <= now
        b = booked.get(t)
        taken = b is not None and b["id"] != exclude_appointment
        slots.append({"time": t, "free": not cancelled and not past and not taken, "past": past,
                      "booked": taken, "token": b["token"] if taken else None,
                      "patient": b["patient"] if taken else None})
    return {"working": True, "cancelled": cancelled, "reason": reason, "clinic": clinic, "slots": slots}


def get_slots(doctor_id: int, date: str) -> dict:
    day = _check_date(date)
    get_doctor(doctor_id)
    with db.connect() as c:
        info = _slots(c, doctor_id, day)
    for s in info["slots"]:  # patients never see other patients' names or tokens
        s.pop("patient", None)
        s.pop("token", None)
    return {"date": date, **info}


def _next_free(c, doctor_id: int) -> str | None:
    today = _now().date()
    for i in range(0, 14):
        day = today + timedelta(days=i)
        for s in _slots(c, doctor_id, day)["slots"]:
            if s["free"]:
                return f"{day.isoformat()} {s['time']}"
    return None


# ============================================================================ appointments
_APPT_SELECT = (
    "SELECT a.*, du.name AS doctor_name, d.user_id AS doctor_user_id, d.category, pu.name AS patient_name, "
    "cl.name AS clinic_name "
    "FROM appointments a JOIN doctors d ON d.id=a.doctor_id JOIN users du ON du.id=d.user_id "
    "JOIN users pu ON pu.id=a.patient_id JOIN clinics cl ON cl.id=a.clinic_id")


def _effective(a: dict) -> dict:
    """Adds 'state': upcoming | completed | cancelled (a confirmed visit in the past is completed)."""
    when = datetime.strptime(f"{a['date']} {a['time']}", "%Y-%m-%d %H:%M")
    raw = a.pop("report_json", "") or ""
    try:
        a["report"] = json.loads(raw) if raw else None
    except ValueError:
        a["report"] = None
    a["state"] = "cancelled" if a["status"] == "cancelled" else ("completed" if when <= _now() else "upcoming")
    return a


def _next_token(c, doctor_id: int, date: str) -> int:
    row = c.execute("SELECT COALESCE(MAX(token),0)+1 AS t FROM appointments WHERE doctor_id=? AND date=?",
                    (doctor_id, date)).fetchone()
    return row["t"]


def _validate_slot(c, doctor_id: int, date: str, time: str, exclude_appointment: int | None = None):
    day, time = _check_date(date), _check_time(time)
    today = _now().date()
    if day < today:
        raise ServiceError("You cannot book a date in the past.")
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise ServiceError(f"Bookings open up to {MAX_DAYS_AHEAD} days ahead.")
    info = _slots(c, doctor_id, day, exclude_appointment)
    if not info["working"]:
        raise ServiceError("The doctor does not see patients on that day.")
    if info["cancelled"]:
        raise ServiceError("The doctor is not available on that day.")
    slot = next((s for s in info["slots"] if s["time"] == time), None)
    if slot is None:
        raise ServiceError("That time is not one of the doctor's slots.")
    if not slot["free"]:
        raise ServiceError("That time slot is no longer free. Please pick another.", 409)
    return day, time, info["clinic"]


def clean_report(report) -> str:
    """Validates the lab-report summary a patient attaches to a booking; returns compact JSON ('' for none)."""
    if not report:
        return ""
    if not isinstance(report, dict) or len(report) > 12:
        raise ServiceError("The attached report summary is not valid.")
    out = {}
    for name, item in report.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise ServiceError("The attached report summary is not valid.")
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError):
            raise ServiceError("The attached report summary is not valid.") from None
        out[name[:30]] = {"value": value, "unit": str(item.get("unit") or "")[:20],
                          "classification": str(item.get("classification") or "")[:40]}
    return json.dumps(out)


def book_appointment(patient_id: int, doctor_id: int, date: str, time: str, reason: str = "",
                     payment_method: str = "cash", report=None) -> dict:
    if payment_method not in ("online", "cash"):
        raise ServiceError("Payment must be 'online' or 'cash'.")
    report_json = clean_report(report)
    doctor = get_doctor(doctor_id)
    try:
        with db.connect() as c:
            day, time, clinic = _validate_slot(c, doctor_id, date, time)
            token = _next_token(c, doctor_id, date)
            status = "paid" if payment_method == "online" else "pending"
            ref = f"DEMO-{db.secrets.token_hex(4).upper()}" if payment_method == "online" else ""
            cur = c.execute(
                "INSERT INTO appointments(patient_id,doctor_id,clinic_id,date,time,token,reason,fee,payment_method,"
                "payment_status,payment_ref,created_at,report_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (patient_id, doctor_id, clinic["id"], date, time, token, (reason or "")[:500], doctor["fee"],
                 payment_method, status, ref, db.now_iso(), report_json))
            appt_id = cur.lastrowid
            patient = c.execute("SELECT name FROM users WHERE id=?", (patient_id,)).fetchone()
            notify(c, patient_id, f"Appointment confirmed with {doctor['name']} on {date} at {time}, "
                                  f"{clinic['name']}. Your token number is {token}.")
            notify(c, doctor["user_id"], f"New appointment: {patient['name']} on {date} at {time} "
                                         f"({clinic['name']}), token {token}." + (" A lab report summary is attached." if report_json else ""))
    except sqlite3.IntegrityError:
        raise ServiceError("That time slot was just taken. Please pick another.", 409) from None
    return get_appointment(appt_id, patient_id)


def get_appointment(appointment_id: int, user_id: int) -> dict:
    with db.connect() as c:
        r = c.execute(_APPT_SELECT + " WHERE a.id=?", (appointment_id,)).fetchone()
        if r is None:
            raise ServiceError("Appointment not found.", 404)
        a = dict(r)
        doctor_user = c.execute("SELECT user_id FROM doctors WHERE id=?", (a["doctor_id"],)).fetchone()["user_id"]
    if user_id not in (a["patient_id"], doctor_user):
        raise ServiceError("Appointment not found.", 404)
    return _effective(a)


def list_appointments(user: dict, state: str = "") -> list:
    """Full history for a patient, or the doctor's own appointments. state: upcoming|completed|cancelled."""
    with db.connect() as c:
        if user["role"] == "patient":
            rows = c.execute(_APPT_SELECT + " WHERE a.patient_id=? ORDER BY a.date DESC, a.time DESC", (user["id"],))
        elif user["role"] == "doctor":
            rows = c.execute(_APPT_SELECT + " WHERE d.user_id=? ORDER BY a.date DESC, a.time DESC", (user["id"],))
        else:
            rows = c.execute(_APPT_SELECT + " ORDER BY a.date DESC, a.time DESC LIMIT 500")
        out = [_effective(dict(r)) for r in rows.fetchall()]
    return [a for a in out if not state or a["state"] == state]


def _load_for_user(c, appointment_id: int, user: dict) -> dict:
    r = c.execute(_APPT_SELECT + " WHERE a.id=?", (appointment_id,)).fetchone()
    if r is None:
        raise ServiceError("Appointment not found.", 404)
    a = dict(r)
    doctor_user = c.execute("SELECT user_id FROM doctors WHERE id=?", (a["doctor_id"],)).fetchone()["user_id"]
    a["doctor_user_id"] = doctor_user
    if user["role"] == "patient" and a["patient_id"] != user["id"]:
        raise ServiceError("Appointment not found.", 404)
    if user["role"] == "doctor" and doctor_user != user["id"]:
        raise ServiceError("Appointment not found.", 404)
    return a


def cancel_appointment(appointment_id: int, user: dict, reason: str = "") -> dict:
    with db.connect() as c:
        a = _load_for_user(c, appointment_id, user)
        if _effective(dict(a))["state"] != "upcoming":
            raise ServiceError("Only an upcoming appointment can be cancelled.")
        who = "the patient" if user["role"] == "patient" else "the doctor"
        c.execute("UPDATE appointments SET status='cancelled', cancel_reason=? WHERE id=?",
                  ((reason or "Cancelled by " + who)[:300], appointment_id))
        refund = " Your online payment will be refunded." if a["payment_status"] == "paid" else ""
        if user["role"] == "patient":
            notify(c, a["doctor_user_id"], f"{a['patient_name']} cancelled the visit on {a['date']} at {a['time']} "
                                           f"(token {a['token']}).")
            notify(c, a["patient_id"], f"You cancelled your visit with {a['doctor_name']} on {a['date']}.{refund}")
        else:
            notify(c, a["patient_id"], f"{a['doctor_name']} cancelled your visit on {a['date']} at {a['time']}.{refund}")
        if a["payment_status"] == "paid":
            c.execute("UPDATE appointments SET payment_status='refunded' WHERE id=?", (appointment_id,))
    return get_appointment(appointment_id, user["id"])


def reschedule_appointment(appointment_id: int, user: dict, date: str, time: str, emergency: bool = False) -> dict:
    """Moves an upcoming appointment to another free slot (the clinic follows the doctor's schedule
    for the chosen day). emergency=True marks it as an emergency postponement."""
    if user["role"] != "patient":
        raise ServiceError("Only the patient can reschedule an appointment.", 403)
    try:
        with db.connect() as c:
            a = _load_for_user(c, appointment_id, user)
            if _effective(dict(a))["state"] != "upcoming":
                raise ServiceError("Only an upcoming appointment can be rescheduled.")
            day, time, clinic = _validate_slot(c, a["doctor_id"], date, time, exclude_appointment=appointment_id)
            if date == a["date"] and time == a["time"]:
                raise ServiceError("That is already your appointment time.")
            token = a["token"] if date == a["date"] else _next_token(c, a["doctor_id"], date)
            c.execute("UPDATE appointments SET date=?, time=?, clinic_id=?, token=?, emergency=? WHERE id=?",
                      (date, time, clinic["id"], token, 1 if emergency else a["emergency"], appointment_id))
            tag = "Emergency postponement" if emergency else "Rescheduled"
            notify(c, a["doctor_user_id"], f"{tag}: {a['patient_name']} moved from {a['date']} {a['time']} to "
                                           f"{date} {time} ({clinic['name']}), token {token}.")
            notify(c, a["patient_id"], f"{tag}: your visit with {a['doctor_name']} is now on {date} at {time}, "
                                       f"{clinic['name']}, token {token}.")
    except sqlite3.IntegrityError:
        raise ServiceError("That time slot was just taken. Please pick another.", 409) from None
    return get_appointment(appointment_id, user["id"])


def delete_appointment(appointment_id: int, user: dict) -> None:
    """Removes an old (completed or cancelled) appointment from the patient's own history."""
    if user["role"] != "patient":
        raise ServiceError("Only the patient can delete a record from their history.", 403)
    with db.connect() as c:
        a = _load_for_user(c, appointment_id, user)
        if _effective(dict(a))["state"] == "upcoming":
            raise ServiceError("Cancel an upcoming appointment before deleting it.")
        c.execute("DELETE FROM appointments WHERE id=?", (appointment_id,))


# ============================================================================ doctor tools
def doctor_week(doctor_id: int, start: str = "") -> dict:
    """Calendar for 7 days: working clinic, whether the day is cancelled, each slot free or booked."""
    first = _check_date(start) if start else _now().date()
    days = []
    with db.connect() as c:
        for i in range(7):
            day = first + timedelta(days=i)
            info = _slots(c, doctor_id, day)
            days.append({"date": day.isoformat(), "weekday": day.strftime("%a"), **info})
    return {"start": first.isoformat(), "days": days}


def doctor_cancel_day(doctor_id: int, date: str, reason: str = "Emergency") -> dict:
    """Emergency: cancels every confirmed appointment on one day and notifies each patient."""
    day = _check_date(date)
    if day < _now().date():
        raise ServiceError("You cannot cancel a day in the past.")
    with db.connect() as c:
        doctor = c.execute("SELECT d.id, u.name FROM doctors d JOIN users u ON u.id=d.user_id WHERE d.id=?",
                           (doctor_id,)).fetchone()
        c.execute("INSERT INTO day_overrides(doctor_id,date,cancelled,reason) VALUES (?,?,1,?) "
                  "ON CONFLICT(doctor_id,date) DO UPDATE SET cancelled=1, reason=excluded.reason",
                  (doctor_id, date, (reason or "Emergency")[:200]))
        rows = c.execute("SELECT id, patient_id, time, payment_status FROM appointments "
                         "WHERE doctor_id=? AND date=? AND status='confirmed'", (doctor_id, date)).fetchall()
        for r in rows:
            c.execute("UPDATE appointments SET status='cancelled', cancel_reason=?, "
                      "payment_status=CASE WHEN payment_status='paid' THEN 'refunded' ELSE payment_status END WHERE id=?",
                      (f"Doctor emergency: {reason or 'Emergency'}"[:300], r["id"]))
            notify(c, r["patient_id"], f"{doctor['name']} had an emergency and cancelled all visits on {date}. "
                                       f"Your {r['time']} appointment is cancelled. Please book a new time.")
    return {"date": date, "cancelled_appointments": len(rows)}


def doctor_reopen_day(doctor_id: int, date: str) -> None:
    _check_date(date)
    with db.connect() as c:
        c.execute("UPDATE day_overrides SET cancelled=0, reason='' WHERE doctor_id=? AND date=?", (doctor_id, date))


def doctor_set_location(doctor_id: int, date: str, clinic_id: int) -> dict:
    """Moves the doctor to another clinic for one day; booked patients are told the new place."""
    day = _check_date(date)
    if day < _now().date():
        raise ServiceError("You cannot change a day in the past.")
    with db.connect() as c:
        clinic = c.execute("SELECT * FROM clinics WHERE id=?", (clinic_id,)).fetchone()
        if clinic is None:
            raise ServiceError("Clinic not found.", 404)
        if _day_info(c, doctor_id, day) is None:
            raise ServiceError("The doctor does not work on that weekday.")
        doctor = c.execute("SELECT u.name FROM doctors d JOIN users u ON u.id=d.user_id WHERE d.id=?",
                           (doctor_id,)).fetchone()
        c.execute("INSERT INTO day_overrides(doctor_id,date,clinic_id) VALUES (?,?,?) "
                  "ON CONFLICT(doctor_id,date) DO UPDATE SET clinic_id=excluded.clinic_id", (doctor_id, date, clinic_id))
        rows = c.execute("SELECT id, patient_id, time FROM appointments WHERE doctor_id=? AND date=? "
                         "AND status='confirmed'", (doctor_id, date)).fetchall()
        for r in rows:
            c.execute("UPDATE appointments SET clinic_id=? WHERE id=?", (clinic_id, r["id"]))
            notify(c, r["patient_id"], f"{doctor['name']} will see patients at {clinic['name']} on {date}. "
                                       f"Your {r['time']} appointment moves there.")
    return {"date": date, "clinic": clinic["name"], "patients_notified": len(rows)}


# ============================================================================ notifications
def list_notifications(user_id: int, limit: int = 50) -> dict:
    with db.connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))]
        unread = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (user_id,)).fetchone()[0]
    return {"unread": unread, "items": rows}


def mark_notifications_read(user_id: int) -> None:
    with db.connect() as c:
        c.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user_id,))


# ============================================================================ messages
def _may_message(c, a: int, b: int) -> bool:
    """A patient and a doctor may talk once they share at least one appointment (past or future)."""
    row = c.execute(
        "SELECT 1 FROM appointments ap JOIN doctors d ON d.id=ap.doctor_id WHERE "
        "(ap.patient_id=? AND d.user_id=?) OR (ap.patient_id=? AND d.user_id=?) LIMIT 1", (a, b, b, a)).fetchone()
    return row is not None


def send_message(sender: dict, receiver_id: int, body: str) -> dict:
    body = (body or "").strip()
    if not body:
        raise ServiceError("Message cannot be empty.")
    if len(body) > 2000:
        raise ServiceError("Message is too long (2000 characters maximum).")
    with db.connect() as c:
        other = c.execute("SELECT id, name, role FROM users WHERE id=? AND active=1", (receiver_id,)).fetchone()
        if other is None or other["role"] not in ("patient", "doctor") or other["role"] == sender["role"]:
            raise ServiceError("You can only message a patient or doctor you have an appointment with.", 403)
        if not _may_message(c, sender["id"], receiver_id):
            raise ServiceError("You can message a doctor after you have booked an appointment with them.", 403)
        cur = c.execute("INSERT INTO messages(sender_id,receiver_id,body,created_at) VALUES (?,?,?,?)",
                        (sender["id"], receiver_id, body, db.now_iso()))
        notify(c, receiver_id, f"New message from {sender['name']}.")
        return dict(c.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone())


def message_thread(user: dict, other_id: int, after_id: int = 0) -> list:
    """Messages between the two users, oldest first. Poll with after_id to get only new ones.
    Messages sent to `user` are marked as read."""
    with db.connect() as c:
        if not _may_message(c, user["id"], other_id):
            return []
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM messages WHERE id>? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) "
            "ORDER BY id", (after_id, user["id"], other_id, other_id, user["id"]))]
        c.execute("UPDATE messages SET read=1 WHERE receiver_id=? AND sender_id=?", (user["id"], other_id))
    return rows


def list_conversations(user: dict) -> list:
    """People this user can talk to (shared appointments), with the last message and unread count."""
    with db.connect() as c:
        if user["role"] == "patient":
            people = c.execute("SELECT DISTINCT u.id, u.name FROM appointments a JOIN doctors d ON d.id=a.doctor_id "
                               "JOIN users u ON u.id=d.user_id WHERE a.patient_id=?", (user["id"],)).fetchall()
        else:
            people = c.execute("SELECT DISTINCT u.id, u.name FROM appointments a JOIN doctors d ON d.id=a.doctor_id "
                               "JOIN users u ON u.id=a.patient_id WHERE d.user_id=?", (user["id"],)).fetchall()
        out = []
        for p in people:
            last = c.execute("SELECT body, created_at FROM messages WHERE (sender_id=? AND receiver_id=?) OR "
                             "(sender_id=? AND receiver_id=?) ORDER BY id DESC LIMIT 1",
                             (user["id"], p["id"], p["id"], user["id"])).fetchone()
            unread = c.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=? AND sender_id=? AND read=0",
                               (user["id"], p["id"])).fetchone()[0]
            out.append({"user_id": p["id"], "name": p["name"], "last_message": last["body"] if last else "",
                        "last_at": last["created_at"] if last else "", "unread": unread})
    return sorted(out, key=lambda x: x["last_at"], reverse=True)


# ============================================================================ blogs and contact
def list_blogs() -> list:
    with db.connect() as c:
        return [dict(r) for r in c.execute("SELECT id,title,category,summary,created_at FROM blogs ORDER BY id DESC")]


def get_blog(blog_id: int) -> dict:
    with db.connect() as c:
        r = c.execute("SELECT * FROM blogs WHERE id=?", (blog_id,)).fetchone()
    if r is None:
        raise ServiceError("Article not found.", 404)
    return dict(r)


def submit_contact(name: str, email: str, message: str) -> None:
    if not (name or "").strip() or not (message or "").strip():
        raise ServiceError("Name and message are required.")
    if not EMAIL_RE.match((email or "").strip()):
        raise ServiceError("Please enter a valid email address.")
    with db.connect() as c:
        c.execute("INSERT INTO contact_messages(name,email,message,created_at) VALUES (?,?,?,?)",
                  (name.strip()[:100], email.strip()[:200], message.strip()[:3000], db.now_iso()))
        for admin in c.execute("SELECT id FROM users WHERE role='admin' AND active=1").fetchall():
            notify(c, admin["id"], f"New contact message from {name.strip()}.")


def list_contact_messages() -> list:
    with db.connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM contact_messages ORDER BY id DESC LIMIT 200")]


# ============================================================================ admin
def admin_overview() -> dict:
    with db.connect() as c:
        one = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "patients": one("SELECT COUNT(*) FROM users WHERE role='patient'"),
            "doctors": one("SELECT COUNT(*) FROM doctors WHERE approved=1"),
            "pending_doctors": one("SELECT COUNT(*) FROM doctors WHERE approved=0"),
            "appointments": one("SELECT COUNT(*) FROM appointments"),
            "upcoming": one("SELECT COUNT(*) FROM appointments WHERE status='confirmed' AND date>=date('now','localtime')"),
            "chat_messages": one("SELECT COUNT(*) FROM chat_messages"),
        }


def admin_list_users() -> list:
    with db.connect() as c:
        rows = c.execute("SELECT u.id,u.email,u.name,u.role,u.active,u.created_at,d.approved,d.id AS doctor_id "
                         "FROM users u LEFT JOIN doctors d ON d.user_id=u.id ORDER BY u.id").fetchall()
    return [dict(r) for r in rows]


def admin_set_doctor_approval(doctor_id: int, approved: bool) -> dict:
    with db.connect() as c:
        d = c.execute("SELECT user_id FROM doctors WHERE id=?", (doctor_id,)).fetchone()
        if d is None:
            raise ServiceError("Doctor not found.", 404)
        c.execute("UPDATE doctors SET approved=? WHERE id=?", (1 if approved else 0, doctor_id))
        notify(c, d["user_id"], "Your doctor account was approved. You can now log in." if approved
               else "Your doctor account is not approved.")
    return get_doctor(doctor_id, include_unapproved=True)


def admin_set_user_active(user_id: int, active: bool, acting_admin_id: int) -> None:
    if user_id == acting_admin_id and not active:
        raise ServiceError("You cannot disable your own account.")
    with db.connect() as c:
        c.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, user_id))


# ============================================================================ AI chat history
def create_conversation(user_id: int, title: str) -> int:
    title = " ".join((title or "New chat").split())[:80] or "New chat"
    with db.connect() as c:
        cur = c.execute("INSERT INTO conversations(user_id,title,created_at,updated_at) VALUES (?,?,?,?)",
                        (user_id, title, db.now_iso(), db.now_iso()))
        return cur.lastrowid


def add_chat_message(conversation_id: int, user_id: int, role: str, content: str, sources: list | None = None,
                     mode: str = "", seconds: float | None = None, verified: bool | None = None) -> int:
    with db.connect() as c:
        if c.execute("SELECT 1 FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone() is None:
            raise ServiceError("Conversation not found.", 404)
        cur = c.execute(
            "INSERT INTO chat_messages(conversation_id,role,content,sources,mode,seconds,verified,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (conversation_id, role, content, "; ".join(sorted(set(sources or []))), mode, seconds,
             None if verified is None else int(verified), db.now_iso()))
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (db.now_iso(), conversation_id))
        return cur.lastrowid


def list_conversations_chat(user_id: int, query: str = "") -> list:
    q = (query or "").strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with db.connect() as c:
        if q:
            rows = c.execute(
                "SELECT * FROM conversations WHERE user_id=? AND (title LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM "
                "chat_messages m WHERE m.conversation_id=conversations.id AND m.content LIKE ? ESCAPE '\\')) "
                "ORDER BY updated_at DESC", (user_id, f"%{q}%", f"%{q}%"))
        else:
            rows = c.execute("SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC", (user_id,))
        return [dict(r) for r in rows]


def chat_messages(conversation_id: int, user_id: int) -> list:
    with db.connect() as c:
        if c.execute("SELECT 1 FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone() is None:
            raise ServiceError("Conversation not found.", 404)
        return [dict(r) for r in c.execute("SELECT * FROM chat_messages WHERE conversation_id=? ORDER BY id",
                                           (conversation_id,))]


def delete_conversation(conversation_id: int, user_id: int) -> None:
    with db.connect() as c:
        c.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))


def set_chat_feedback(message_id: int, user_id: int, value: int | None) -> None:
    if value not in (1, -1, None):
        raise ServiceError("Feedback must be 1, -1 or null.")
    with db.connect() as c:
        row = c.execute("SELECT m.id FROM chat_messages m JOIN conversations cv ON cv.id=m.conversation_id "
                        "WHERE m.id=? AND cv.user_id=? AND m.role='assistant'", (message_id, user_id)).fetchone()
        if row is None:
            raise ServiceError("Message not found.", 404)
        c.execute("UPDATE chat_messages SET feedback=? WHERE id=?", (value, message_id))


def feedback_stats() -> dict:
    with db.connect() as c:
        r = c.execute("SELECT SUM(feedback=1) AS up, SUM(feedback=-1) AS down, COUNT(*) AS answers "
                      "FROM chat_messages WHERE role='assistant'").fetchone()
    return {"helpful": r["up"] or 0, "not_helpful": r["down"] or 0, "answers": r["answers"] or 0}


# ============================================================================ visit notes (doctor)
def add_visit_notes(user: dict, appointment_id: int, notes: str) -> dict:
    notes = (notes or "").strip()
    if not notes:
        raise ServiceError("Please write the visit notes.")
    with db.connect() as c:
        a = _load_for_user(c, appointment_id, user)
        if user["role"] != "doctor":
            raise ServiceError("Only the doctor can add visit notes.", 403)
        if a["status"] == "cancelled":
            raise ServiceError("This appointment was cancelled.")
        if datetime.strptime(a["date"], "%Y-%m-%d").date() > _now().date():
            raise ServiceError("Visit notes can be added on or after the appointment day.")
        c.execute("UPDATE appointments SET doctor_notes=? WHERE id=?", (notes[:3000], appointment_id))
        notify(c, a["patient_id"], f"{a['doctor_name']} added notes to your visit on {a['date']}.")
    return get_appointment(appointment_id, user["id"])


# ============================================================================ availability calendar
def doctor_availability(doctor_id: int, start: str = "", days: int = 35) -> list:
    """One entry per day for the booking calendar: working?, cancelled?, free/total slots, clinic."""
    get_doctor(doctor_id)
    first = _check_date(start) if start else _now().date()
    days = max(1, min(int(days), MAX_DAYS_AHEAD))
    out = []
    with db.connect() as c:
        for i in range(days):
            day = first + timedelta(days=i)
            info = _slots(c, doctor_id, day)
            free = sum(1 for s in info["slots"] if s["free"])
            total = len(info["slots"])
            if not info["working"]:
                status = "off"
            elif info["cancelled"]:
                status = "cancelled"
            elif free == 0:
                status = "full"
            else:
                status = "free"
            out.append({"date": day.isoformat(), "weekday": day.strftime("%a"), "status": status, "free": free,
                        "total": total, "clinic": (info["clinic"] or {}).get("name")})
    return out


# ============================================================================ blogs (admin)
def _blog_fields(title, category, summary, body):
    title = (title or "").strip()
    if not title or not (body or "").strip():
        raise ServiceError("A blog needs a title and some text.")
    return title[:150], (category or "").strip()[:40], (summary or "").strip()[:300], body.strip()[:20000]


def create_blog(title: str, category: str, summary: str, body: str) -> dict:
    t, cat, sm, b = _blog_fields(title, category, summary, body)
    with db.connect() as c:
        cur = c.execute("INSERT INTO blogs(title,category,summary,body,created_at) VALUES (?,?,?,?,?)",
                        (t, cat, sm, b, db.now_iso()))
        return {"id": cur.lastrowid}


def update_blog(blog_id: int, title: str, category: str, summary: str, body: str) -> dict:
    t, cat, sm, b = _blog_fields(title, category, summary, body)
    with db.connect() as c:
        cur = c.execute("UPDATE blogs SET title=?,category=?,summary=?,body=? WHERE id=?", (t, cat, sm, b, blog_id))
        if cur.rowcount == 0:
            raise ServiceError("Article not found.", 404)
    return get_blog(blog_id)


def delete_blog(blog_id: int) -> None:
    with db.connect() as c:
        c.execute("DELETE FROM blogs WHERE id=?", (blog_id,))


# ============================================================================ own profile
def update_profile(user_id: int, name: str | None = None, diabetes_type: str | None = None) -> dict:
    with db.connect() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise ServiceError("User not found.", 404)
        if name is not None:
            if not name.strip():
                raise ServiceError("Name cannot be empty.")
            c.execute("UPDATE users SET name=? WHERE id=?", (name.strip()[:100], user_id))
        if diabetes_type is not None and row["role"] == "patient":
            if diabetes_type and diabetes_type not in DIABETES_TYPES:
                raise ServiceError("Please choose a valid diabetes type.")
            c.execute("UPDATE users SET diabetes_type=? WHERE id=?", (diabetes_type, user_id))
        return _user_public(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def change_password(user_id: int, old_password: str, new_password: str) -> None:
    if len(new_password or "") < 6:
        raise ServiceError("Password must be at least 6 characters.")
    with db.connect() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None or not db.verify_password(old_password or "", row["password_hash"]):
            raise ServiceError("Your current password is not correct.", 403)
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (db.hash_password(new_password), user_id))
