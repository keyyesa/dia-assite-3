"""Tests for accounts, doctors, booking, emergencies, messages and chat history.
Run from the backend folder:  python -m unittest discover -s tests -v
Standard library only; every test uses its own temporary database."""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import db, seed, services  # noqa: E402
from api.services import ServiceError  # noqa: E402


def next_weekday(weekday: int, min_days: int = 2) -> str:
    d = date.today() + timedelta(days=min_days)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d.isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DIAASSIST_DB"] = os.path.join(self.tmp, "t.db")
        os.environ["DIAASSIST_SECRET"] = "test-secret"
        db._ready.clear()
        seed.seed_all()
        self.patient = services.login("patient@diaassist.ai", "patient123")["user"]
        self.sana = next(d for d in services.list_doctors() if d["name"] == "Dr. Sana Malik")
        self.sana_user = services.login("sana.malik@diaassist.ai", "doctor123")["user"]
        self.sana_user["doctor_id"] = self.sana["id"]
        self.monday = next_weekday(0)  # Dr. Sana: City Hospital 09:00-13:00

    def book(self, time="09:00", day=None, payment="cash", patient=None):
        return services.book_appointment((patient or self.patient)["id"], self.sana["id"], day or self.monday, time,
                                         "review report", payment)


class AccountTests(Base):
    def test_password_is_hashed_and_login_works(self):
        with db.connect() as c:
            stored = c.execute("SELECT password_hash FROM users WHERE email='patient@diaassist.ai'").fetchone()[0]
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertNotIn("patient123", stored)
        with self.assertRaises(ServiceError):
            services.login("patient@diaassist.ai", "wrong")

    def test_token_round_trip_and_tamper(self):
        res = services.login("patient@diaassist.ai", "patient123")
        self.assertEqual(services.user_from_token(res["token"])["email"], "patient@diaassist.ai")
        self.assertIsNone(services.user_from_token(res["token"] + "x"))
        self.assertIsNone(services.user_from_token("garbage"))

    def test_signup_validation_and_duplicates(self):
        services.register_patient("new@x.com", "New Person", "secret1", "Type 2 diabetes")
        with self.assertRaises(ServiceError) as e:
            services.register_patient("NEW@x.com", "Again", "secret1")
        self.assertEqual(e.exception.status, 409)
        for args in (("bad-email", "A", "secret1"), ("a@b.co", "", "secret1"), ("a@b.co", "A", "123")):
            with self.assertRaises(ServiceError):
                services.register_patient(*args)

    def test_role_pages_are_separate(self):
        with self.assertRaises(ServiceError) as e:
            services.login("patient@diaassist.ai", "patient123", role="doctor")
        self.assertEqual(e.exception.status, 403)
        services.login("sana.malik@diaassist.ai", "doctor123", role="doctor")

    def test_new_doctor_needs_admin_approval(self):
        services.register_doctor("new.doc@x.com", "Dr. New", "secret1", "Endocrinology", "MBBS", 1800, 3)
        with self.assertRaises(ServiceError) as e:
            services.login("new.doc@x.com", "secret1")
        self.assertIn("approval", e.exception.message)
        self.assertNotIn("Dr. New", [d["name"] for d in services.list_doctors()])
        admin = services.login("admin@diaassist.ai", "admin123")["user"]
        self.assertEqual(services.list_notifications(admin["id"])["unread"], 1)
        pending = next(u for u in services.admin_list_users() if u["email"] == "new.doc@x.com")
        services.admin_set_doctor_approval(pending["doctor_id"], True)
        services.login("new.doc@x.com", "secret1")
        self.assertIn("Dr. New", [d["name"] for d in services.list_doctors()])


class DoctorTests(Base):
    def test_filters(self):
        self.assertEqual(len(services.list_doctors()), 6)
        self.assertEqual({d["category"] for d in services.list_doctors(category="Eye care")}, {"Eye care"})
        self.assertTrue(all(d["fee"] <= 1500 for d in services.list_doctors(max_fee=1500)))
        self.assertTrue(all(any(c["name"] == "Home Visit" for c in d["clinics"])
                            for d in services.list_doctors(clinic="Home Visit")))
        self.assertEqual(services.list_doctors(q="Sana")[0]["name"], "Dr. Sana Malik")

    def test_slots_follow_schedule(self):
        info = services.get_slots(self.sana["id"], self.monday)
        self.assertEqual(info["clinic"]["name"], "City Hospital")
        self.assertEqual([s["time"] for s in info["slots"]][:2], ["09:00", "09:30"])
        self.assertEqual(len(info["slots"]), 8)
        self.assertTrue(all(s["free"] for s in info["slots"]))
        saturday = services.get_slots(self.sana["id"], next_weekday(5))
        self.assertFalse(saturday["working"])


class BookingTests(Base):
    def test_booking_gives_token_notifications_and_payment(self):
        a = self.book("09:00", payment="online")
        self.assertEqual(a["token"], 1)
        self.assertEqual(a["payment_status"], "paid")
        self.assertTrue(a["payment_ref"].startswith("DEMO-"))
        self.assertEqual(a["clinic_name"], "City Hospital")
        self.assertEqual(self.book("09:30", payment="cash")["payment_status"], "pending")
        self.assertEqual(services.list_notifications(self.patient["id"])["unread"], 2)
        self.assertEqual(services.list_notifications(self.sana["user_id"])["unread"], 2)

    def test_booked_slot_is_busy_and_cannot_be_double_booked(self):
        self.book("10:00")
        slots = {s["time"]: s for s in services.get_slots(self.sana["id"], self.monday)["slots"]}
        self.assertFalse(slots["10:00"]["free"])
        self.assertNotIn("patient", slots["10:00"])  # privacy: no other patient's name
        other = services.register_patient("p2@x.com", "Second Patient", "secret1")
        with self.assertRaises(ServiceError) as e:
            self.book("10:00", patient=other)
        self.assertEqual(e.exception.status, 409)

    def test_rejects_bad_input(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        for day, time in ((past, "09:00"), (self.monday, "09:15"), (self.monday, "bad"), (next_weekday(5), "09:00"),
                          ("2026-13-45", "09:00"), ((date.today() + timedelta(days=200)).isoformat(), "09:00")):
            with self.subTest(day=day, time=time), self.assertRaises(ServiceError):
                services.book_appointment(self.patient["id"], self.sana["id"], day, time)
        with self.assertRaises(ServiceError):
            services.book_appointment(self.patient["id"], self.sana["id"], self.monday, "09:00", "", "bitcoin")

    def test_cancel_frees_slot_and_keeps_history(self):
        a = self.book("09:00", payment="online")
        done = services.cancel_appointment(a["id"], self.patient, "plans changed")
        self.assertEqual(done["state"], "cancelled")
        self.assertEqual(done["payment_status"], "refunded")
        self.assertTrue(next(s for s in services.get_slots(self.sana["id"], self.monday)["slots"]
                             if s["time"] == "09:00")["free"])
        self.assertEqual(len(services.list_appointments(self.patient)), 1)
        self.assertEqual(self.book("09:00")["token"], 2)  # tokens are never reused on a day
        with self.assertRaises(ServiceError):
            services.cancel_appointment(a["id"], self.patient)  # already cancelled

    def test_reschedule_and_emergency_postpone(self):
        a = self.book("09:00")
        moved = services.reschedule_appointment(a["id"], self.patient, self.monday, "11:00")
        self.assertEqual(moved["time"], "11:00")
        self.assertEqual(moved["token"], 1)
        wednesday = next_weekday(2)
        em = services.reschedule_appointment(a["id"], self.patient, wednesday, "09:30", emergency=True)
        self.assertEqual((em["date"], em["emergency"]), (wednesday, 1))
        with self.assertRaises(ServiceError):
            services.reschedule_appointment(a["id"], self.patient, wednesday, "09:30")  # same time
        self.assertIn("Emergency postponement", services.list_notifications(self.sana["user_id"])["items"][0]["text"])
        # old slot is free again
        self.assertTrue(next(s for s in services.get_slots(self.sana["id"], self.monday)["slots"]
                             if s["time"] == "11:00")["free"])

    def test_reschedule_into_taken_slot_is_refused(self):
        a = self.book("09:00")
        self.book("10:00", patient=services.register_patient("p3@x.com", "Third", "secret1"))
        with self.assertRaises(ServiceError):
            services.reschedule_appointment(a["id"], self.patient, self.monday, "10:00")

    def test_delete_only_old_records_and_only_own(self):
        a = self.book("09:00")
        with self.assertRaises(ServiceError):
            services.delete_appointment(a["id"], self.patient)  # still upcoming
        services.cancel_appointment(a["id"], self.patient)
        stranger = services.register_patient("s@x.com", "Stranger", "secret1")
        with self.assertRaises(ServiceError):
            services.delete_appointment(a["id"], stranger)
        services.delete_appointment(a["id"], self.patient)
        self.assertEqual(services.list_appointments(self.patient), [])

    def test_patients_cannot_see_each_others_appointments(self):
        a = self.book("09:00")
        stranger = services.register_patient("s2@x.com", "Stranger", "secret1")
        with self.assertRaises(ServiceError):
            services.get_appointment(a["id"], stranger["id"])
        with self.assertRaises(ServiceError):
            services.cancel_appointment(a["id"], stranger)


class DoctorToolTests(Base):
    def test_emergency_cancel_whole_day(self):
        a1, a2 = self.book("09:00", payment="online"), self.book("10:00")
        res = services.doctor_cancel_day(self.sana["id"], self.monday, "family emergency")
        self.assertEqual(res["cancelled_appointments"], 2)
        for a in (a1, a2):
            self.assertEqual(services.get_appointment(a["id"], self.patient["id"])["state"], "cancelled")
        self.assertEqual(services.get_appointment(a1["id"], self.patient["id"])["payment_status"], "refunded")
        info = services.get_slots(self.sana["id"], self.monday)
        self.assertTrue(info["cancelled"])
        self.assertFalse(any(s["free"] for s in info["slots"]))
        with self.assertRaises(ServiceError):
            self.book("11:00")
        self.assertIn("emergency", services.list_notifications(self.patient["id"])["items"][0]["text"])
        services.doctor_reopen_day(self.sana["id"], self.monday)
        self.assertTrue(any(s["free"] for s in services.get_slots(self.sana["id"], self.monday)["slots"]))

    def test_location_change_moves_booked_patients(self):
        a = self.book("09:00")
        care = next(c for c in services.list_clinics() if c["name"] == "Care Clinic")
        res = services.doctor_set_location(self.sana["id"], self.monday, care["id"])
        self.assertEqual(res["patients_notified"], 1)
        self.assertEqual(services.get_appointment(a["id"], self.patient["id"])["clinic_name"], "Care Clinic")
        self.assertEqual(services.get_slots(self.sana["id"], self.monday)["clinic"]["name"], "Care Clinic")
        self.assertEqual(self.book("10:00")["clinic_name"], "Care Clinic")

    def test_doctor_week_shows_busy_and_free(self):
        self.book("09:00")
        week = services.doctor_week(self.sana["id"], self.monday)
        day = week["days"][0]
        self.assertEqual(day["slots"][0]["booked"], True)
        self.assertEqual(day["slots"][0]["patient"], "Ali Hassan")
        self.assertEqual(day["slots"][0]["token"], 1)
        self.assertEqual(day["slots"][1]["free"], True)
        self.assertEqual(len(week["days"]), 7)

    def test_doctor_can_cancel_own_appointment_only(self):
        a = self.book("09:00")
        services.cancel_appointment(a["id"], self.sana_user, "running late")
        other_doc = services.login("usman.raza@diaassist.ai", "doctor123")["user"]
        b = self.book("10:00")
        with self.assertRaises(ServiceError):
            services.cancel_appointment(b["id"], other_doc)


class MessageTests(Base):
    def test_messaging_needs_a_shared_appointment(self):
        with self.assertRaises(ServiceError) as e:
            services.send_message(self.patient, self.sana["user_id"], "Hello")
        self.assertEqual(e.exception.status, 403)
        self.book("09:00")
        services.send_message(self.patient, self.sana["user_id"], "Can I send my report?")
        services.send_message(self.sana_user, self.patient["id"], "Yes, please.")
        thread = services.message_thread(self.sana_user, self.patient["id"])
        self.assertEqual([m["body"] for m in thread], ["Can I send my report?", "Yes, please."])
        self.assertEqual(services.message_thread(self.sana_user, self.patient["id"], after_id=thread[0]["id"])[0]["body"],
                         "Yes, please.")
        convo = services.list_conversations(self.sana_user)
        self.assertEqual(convo[0]["name"], "Ali Hassan")
        self.assertEqual(convo[0]["unread"], 0)

    def test_unread_count_and_validation(self):
        self.book("09:00")
        services.send_message(self.patient, self.sana["user_id"], "Hi")
        self.assertEqual(services.list_conversations(self.sana_user)[0]["unread"], 1)
        for body in ("", "   ", "x" * 2001):
            with self.assertRaises(ServiceError):
                services.send_message(self.patient, self.sana["user_id"], body)
        with self.assertRaises(ServiceError):
            services.send_message(self.patient, self.patient["id"], "to myself")
        stranger = services.register_patient("s3@x.com", "Stranger", "secret1")
        self.assertEqual(services.message_thread(stranger, self.sana["user_id"]), [])


class ContentTests(Base):
    def test_blogs_and_contact(self):
        self.assertEqual(len(services.list_blogs()), 4)
        self.assertIn("HbA1c", services.get_blog(services.list_blogs()[-1]["id"])["body"])
        with self.assertRaises(ServiceError):
            services.get_blog(9999)
        services.submit_contact("Sam", "sam@x.com", "Hello team")
        self.assertEqual(len(services.list_contact_messages()), 1)
        with self.assertRaises(ServiceError):
            services.submit_contact("Sam", "bad", "Hello")

    def test_seed_is_idempotent(self):
        seed.seed_all()
        self.assertEqual(len(services.list_doctors()), 6)
        self.assertEqual(len(services.list_blogs()), 4)


class ChatHistoryTests(Base):
    def test_history_search_feedback_and_isolation(self):
        cid = services.create_conversation(self.patient["id"], "What does HbA1c 7.8 mean?")
        services.add_chat_message(cid, self.patient["id"], "user", "What does HbA1c 7.8 mean?")
        mid = services.add_chat_message(cid, self.patient["id"], "assistant", "It is in the diabetes range.",
                                        ["ADA.pdf"], "fast", 3.2, True)
        services.set_chat_feedback(mid, self.patient["id"], 1)
        self.assertEqual(services.feedback_stats()["helpful"], 1)
        self.assertEqual(len(services.list_conversations_chat(self.patient["id"], "hba1c")), 1)
        self.assertEqual(len(services.list_conversations_chat(self.patient["id"], "diabetes range")), 1)
        self.assertEqual(services.list_conversations_chat(self.patient["id"], "100%_"), [])
        stranger = services.register_patient("s4@x.com", "Stranger", "secret1")
        with self.assertRaises(ServiceError):
            services.chat_messages(cid, stranger["id"])
        with self.assertRaises(ServiceError):
            services.set_chat_feedback(mid, stranger["id"], -1)
        services.delete_conversation(cid, self.patient["id"])
        self.assertEqual(services.list_conversations_chat(self.patient["id"]), [])


class Day1ExtrasTests(Base):
    REPORT = {"HbA1c": {"value": 8.1, "unit": "%", "classification": "diabetes_range"},
              "LDL": {"value": 130, "unit": "mg/dL", "classification": "borderline"}}

    def test_report_attached_to_booking_and_visible_to_doctor(self):
        a = services.book_appointment(self.patient["id"], self.sana["id"], self.monday, "09:00", "", "cash", self.REPORT)
        self.assertEqual(a["report"]["HbA1c"]["classification"], "diabetes_range")
        mine = services.list_appointments(self.sana_user)
        self.assertEqual(mine[0]["report"]["LDL"]["value"], 130.0)
        self.assertTrue(any("report summary" in n["text"] for n in services.list_notifications(self.sana_user["id"])["items"]))
        self.assertIsNone(self.book("09:30")["report"])

    def test_invalid_report_rejected(self):
        with self.assertRaises(ServiceError):
            services.book_appointment(self.patient["id"], self.sana["id"], self.monday, "09:00", "", "cash", {"HbA1c": "high"})
        with self.assertRaises(ServiceError):
            services.book_appointment(self.patient["id"], self.sana["id"], self.monday, "09:00", "", "cash",
                                      {"HbA1c": {"value": "abc"}})

    def test_appointment_has_doctor_user_id_for_messaging(self):
        a = self.book()
        self.assertEqual(a["doctor_user_id"], self.sana_user["id"])

    def test_visit_notes(self):
        a = self.book()
        with self.assertRaises(ServiceError):  # future day
            services.add_visit_notes(self.sana_user, a["id"], "Start metformin")
        with db.connect() as c:
            c.execute("UPDATE appointments SET date=? WHERE id=?", (date.today().isoformat(), a["id"]))
        done = services.add_visit_notes(self.sana_user, a["id"], "Start metformin")
        self.assertEqual(done["doctor_notes"], "Start metformin")
        with self.assertRaises(ServiceError):
            services.add_visit_notes(self.patient, a["id"], "I am the patient")
        with self.assertRaises(ServiceError):
            services.add_visit_notes(self.sana_user, a["id"], "  ")

    def test_availability_calendar(self):
        days = services.doctor_availability(self.sana["id"], days=21)
        self.assertEqual(len(days), 21)
        mon = next(d for d in days if d["date"] == self.monday)
        self.assertEqual(mon["status"], "free")
        self.assertGreater(mon["free"], 0)
        self.assertTrue(any(d["status"] == "off" for d in days))
        services.doctor_cancel_day(self.sana["id"], self.monday, "Emergency")
        again = next(d for d in services.doctor_availability(self.sana["id"], days=21) if d["date"] == self.monday)
        self.assertEqual(again["status"], "cancelled")

    def test_blog_crud(self):
        new = services.create_blog("Walking daily", "Lifestyle", "Short walks help.", "Walk 30 minutes.")
        self.assertEqual(services.get_blog(new["id"])["title"], "Walking daily")
        services.update_blog(new["id"], "Walking every day", "Lifestyle", "Short walks help.", "Walk 30 minutes.")
        self.assertEqual(services.get_blog(new["id"])["title"], "Walking every day")
        services.delete_blog(new["id"])
        with self.assertRaises(ServiceError):
            services.get_blog(new["id"])
        with self.assertRaises(ServiceError):
            services.create_blog("", "x", "y", "z")

    def test_profile_and_password(self):
        u = services.update_profile(self.patient["id"], "Ayesha Khan", "Pre-diabetes")
        self.assertEqual((u["name"], u["diabetes_type"]), ("Ayesha Khan", "Pre-diabetes"))
        with self.assertRaises(ServiceError):
            services.update_profile(self.patient["id"], "", None)
        with self.assertRaises(ServiceError):
            services.change_password(self.patient["id"], "wrong", "newsecret")
        with self.assertRaises(ServiceError):
            services.change_password(self.patient["id"], "patient123", "123")
        services.change_password(self.patient["id"], "patient123", "newsecret")
        self.assertEqual(services.login("patient@diaassist.ai", "newsecret")["user"]["name"], "Ayesha Khan")
        with self.assertRaises(ServiceError):
            services.login("patient@diaassist.ai", "patient123")

    def test_old_database_is_migrated(self):
        import sqlite3
        old = os.path.join(self.tmp, "old.db")
        conn = sqlite3.connect(old)
        conn.executescript(db.SCHEMA.replace("    report_json TEXT DEFAULT '',\n", "").replace("    doctor_notes TEXT DEFAULT '',\n", ""))
        conn.execute("ALTER TABLE appointments RENAME TO appt_old")
        conn.execute("CREATE TABLE appointments (id INTEGER PRIMARY KEY, patient_id INT, doctor_id INT, clinic_id INT, date TEXT, time TEXT, status TEXT, token INT, reason TEXT, fee INT, payment_method TEXT, payment_status TEXT, payment_ref TEXT, cancel_reason TEXT, emergency INT, created_at TEXT)")
        conn.commit(); conn.close()
        os.environ["DIAASSIST_DB"] = old
        db._ready.clear()
        with db.connect() as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(appointments)")}
        self.assertTrue({"report_json", "doctor_notes"} <= cols)


if __name__ == "__main__":
    unittest.main()
