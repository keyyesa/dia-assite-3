"""SQLite storage for DiaAssist: accounts, doctors, appointments, messages, notifications,
blogs, contact messages and AI chat history. Standard library only.

Passwords are salted and hashed with scrypt. Login sessions use a signed token (HMAC-SHA256)
so no extra packages are needed. Card numbers are never stored (payments are a demo).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('patient','doctor','admin')),
    password_hash TEXT NOT NULL,
    diabetes_type TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clinics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    qualification TEXT DEFAULT '',
    experience_years INTEGER DEFAULT 0,
    fee INTEGER NOT NULL DEFAULT 0,
    bio TEXT DEFAULT '',
    approved INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    clinic_id INTEGER NOT NULL REFERENCES clinics(id),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    slot_minutes INTEGER NOT NULL DEFAULT 30,
    UNIQUE (doctor_id, weekday)
);
CREATE TABLE IF NOT EXISTS day_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    clinic_id INTEGER REFERENCES clinics(id),
    cancelled INTEGER NOT NULL DEFAULT 0,
    reason TEXT DEFAULT '',
    UNIQUE (doctor_id, date)
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    clinic_id INTEGER NOT NULL REFERENCES clinics(id),
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','cancelled')),
    token INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    fee INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT NOT NULL DEFAULT 'cash' CHECK (payment_method IN ('online','cash')),
    payment_status TEXT NOT NULL DEFAULT 'pending',
    payment_ref TEXT DEFAULT '',
    cancel_reason TEXT DEFAULT '',
    emergency INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (doctor_id, date, token)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_slot ON appointments(doctor_id, date, time) WHERE status = 'confirmed';
CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appt_doctor_date ON appointments(doctor_id, date);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_pair ON messages(sender_id, receiver_id);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read);
CREATE TABLE IF NOT EXISTS blogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    body TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    sources TEXT DEFAULT '',
    mode TEXT DEFAULT '',
    seconds REAL,
    verified INTEGER,
    feedback INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_conv ON chat_messages(conversation_id);
"""

_lock = threading.RLock()
_ready = set()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def db_path() -> str:
    return os.environ.get("DIAASSIST_DB") or os.path.join(DATA_DIR, "diaassist.db")


def _migrate(conn) -> None:
    """Adds columns introduced after the first release, so older database files keep working."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(appointments)")}
    for name in ("report_json", "doctor_notes"):
        if name not in cols:
            conn.execute(f"ALTER TABLE appointments ADD COLUMN {name} TEXT DEFAULT ''")
    conn.commit()


@contextmanager
def connect():
    """One connection per call. Commits on success, rolls back on error."""
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with _lock:
            if path not in _ready:
                conn.executescript(SCHEMA)
                _migrate(conn)
                _ready.add(path)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ----------------------------------------------------------------------------- passwords
def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = hash_password(password, bytes.fromhex(salt_hex)).split("$")[2]
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------------------------- tokens
def _secret() -> bytes:
    env = os.environ.get("DIAASSIST_SECRET")
    if env:
        return env.encode("utf-8")
    path = os.path.join(os.path.dirname(db_path()), "secret.key")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(secrets.token_bytes(32))
    with open(path, "rb") as f:
        return f.read()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user_id: int, role: str, ttl_seconds: int = 7 * 24 * 3600) -> str:
    payload = _b64(json.dumps({"uid": user_id, "role": role, "exp": int(time.time()) + ttl_seconds}).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str) -> dict | None:
    """Returns {'uid','role','exp'} for a valid, unexpired token, else None."""
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        return data if data.get("exp", 0) >= time.time() else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
