"""Demo data: clinics, sample doctors with weekly schedules, three accounts and sample blog posts.

Everything created here is marked as demo data (doctors have is_demo=1). It only runs when the
tables are empty, so it never overwrites real data. Change the demo passwords before real use.
"""
import os

from api import db, services

CLINICS = [
    ("City Hospital", "Main Boulevard"),
    ("Care Clinic", "Garden Town"),
    ("Home Visit", "At the patient's home"),
]

# name, email, category, qualification, years, fee, bio, schedule {weekday: (clinic, start, end)}
DOCTORS = [
    ("Dr. Sana Malik", "sana.malik@diaassist.ai", "Endocrinology", "MBBS, FCPS (Endocrinology)", 12, 2500,
     "Type 2 diabetes control, insulin therapy and diabetes in pregnancy.",
     {0: ("City Hospital", "09:00", "13:00"), 2: ("City Hospital", "09:00", "13:00"),
      1: ("Care Clinic", "16:00", "19:00"), 3: ("Care Clinic", "16:00", "19:00"), 4: ("Home Visit", "10:00", "12:00")}),
    ("Dr. Usman Raza", "usman.raza@diaassist.ai", "Endocrinology", "MBBS, MD (Medicine)", 9, 2000,
     "Adult diabetes, thyroid problems and long-term follow-up.",
     {0: ("City Hospital", "14:00", "18:00"), 1: ("City Hospital", "14:00", "18:00"), 3: ("City Hospital", "10:00", "13:00")}),
    ("Dr. Farah Noor", "farah.noor@diaassist.ai", "Diabetes educator", "MSc Diabetes Care", 7, 1500,
     "Teaching glucose monitoring, insulin technique and daily self-care.",
     {0: ("Care Clinic", "17:00", "20:00"), 2: ("Care Clinic", "17:00", "20:00"), 5: ("Home Visit", "10:00", "13:00")}),
    ("Dr. Hamza Qureshi", "hamza.qureshi@diaassist.ai", "Nutrition", "BSc, MSc Clinical Nutrition", 6, 1200,
     "Meal planning for diabetes and weight management.",
     {1: ("Care Clinic", "11:00", "15:00"), 3: ("Care Clinic", "11:00", "15:00")}),
    ("Dr. Ayesha Tariq", "ayesha.tariq@diaassist.ai", "Eye care", "MBBS, FCPS (Ophthalmology)", 11, 2200,
     "Diabetic retinopathy screening and treatment.",
     {2: ("City Hospital", "09:00", "12:00"), 4: ("City Hospital", "09:00", "12:00")}),
    ("Dr. Bilal Ahmed", "bilal.ahmed@diaassist.ai", "Kidney care", "MBBS, FCPS (Nephrology)", 14, 3000,
     "Diabetic kidney disease and albumin in urine.",
     {3: ("City Hospital", "15:00", "18:00"), 4: ("Care Clinic", "15:00", "18:00")}),
]

BLOGS = [
    ("Tests", "What your HbA1c number means",
     "Ranges, how often to test and what changes the result.",
     "HbA1c shows your average blood sugar over about three months. Below 5.7% is normal, 5.7% to 6.4% is "
     "prediabetes and 6.5% or higher is in the diabetes range. Many adults with diabetes are advised to test every "
     "3 to 6 months, and your doctor sets a personal target. Sample article for the prototype."),
    ("Daily life", "Meals, activity and blood sugar",
     "Simple habits that help type 2 diabetes control.",
     "Regular movement, steady meal times and fewer sugary drinks all help. Guidelines suggest at least 150 minutes "
     "of moderate activity a week for most adults. Ask your doctor or dietitian before changing medicines or "
     "meals. Sample article for the prototype."),
    ("Complications", "When to see a doctor about your feet",
     "Warning signs of neuropathy and wounds that heal slowly.",
     "Check your feet every day. See a doctor soon for a sore that does not heal, numbness, burning pain, "
     "swelling or a change in skin colour. Sample article for the prototype."),
    ("Kidneys", "Why your doctor checks urine albumin",
     "A small leak of albumin can be an early sign of kidney damage.",
     "Diabetes can slowly damage the kidneys. A yearly urine albumin test finds problems early, when treatment "
     "works best. Sample article for the prototype."),
]


def seed_all() -> None:
    """Idempotent: safe to call on every start."""
    with db.connect() as c:
        for name, address in CLINICS:
            c.execute("INSERT OR IGNORE INTO clinics(name,address) VALUES (?,?)", (name, address))
        clinic_ids = {r["name"]: r["id"] for r in c.execute("SELECT id,name FROM clinics")}
        has_blogs = c.execute("SELECT COUNT(*) FROM blogs").fetchone()[0]
        if not has_blogs:
            for category, title, summary, body in BLOGS:
                c.execute("INSERT INTO blogs(title,category,summary,body,created_at) VALUES (?,?,?,?,?)",
                          (title, category, summary, body, db.now_iso()))

    def ensure_user(email, name, pw, role, dtype=""):
        with db.connect() as c:
            if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                return
            c.execute("INSERT INTO users(email,name,role,password_hash,diabetes_type,created_at) VALUES (?,?,?,?,?,?)",
                      (email, name, role, db.hash_password(pw), dtype, db.now_iso()))

    ensure_user("admin@diaassist.ai", "System Administrator", os.environ.get("ADMIN_PASSWORD", "admin123"), "admin")
    ensure_user("patient@diaassist.ai", "Ali Hassan", "patient123", "patient", "Type 2 diabetes")

    for name, email, category, qual, years, fee, bio, schedule in DOCTORS:
        ensure_user(email, name, "doctor123", "doctor")
        with db.connect() as c:
            uid = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
            if c.execute("SELECT 1 FROM doctors WHERE user_id=?", (uid,)).fetchone():
                continue
            cur = c.execute("INSERT INTO doctors(user_id,category,qualification,experience_years,fee,bio,approved,is_demo)"
                            " VALUES (?,?,?,?,?,?,1,1)", (uid, category, qual, years, fee, bio))
            doctor_id = cur.lastrowid
        for weekday, (clinic, start, end) in schedule.items():
            services.set_schedule(doctor_id, weekday, clinic_ids[clinic], start, end, 30)
