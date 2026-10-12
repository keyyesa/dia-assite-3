import unittest

from src.agents.report_analysis import analyze_report_detailed

REPORT = """Patient lab report
HbA1c: 7.2 %
Fasting Blood Glucose: 132 mg/dL
LDL Cholesterol: 130 mg/dL
HDL Cholesterol: 38 mg/dL
Triglycerides: 180 mg/dL
"""


class LipidNoteTests(unittest.TestCase):
    def setUp(self):
        self.values = analyze_report_detailed(REPORT)["values"]

    def test_lipids_carry_a_note(self):
        for p in ("LDL", "HDL", "Triglycerides"):
            self.assertIn(p, self.values)
            self.assertTrue(self.values[p].get("note"), p)
        self.assertIn("your doctor decides", self.values["LDL"]["note"])

    def test_glucose_values_have_no_note(self):
        for p in ("HbA1c", "FBG"):
            self.assertNotIn("note", self.values[p])

    def test_classification_unchanged(self):
        self.assertEqual(self.values["HDL"]["classification"], "low")
        self.assertEqual(self.values["FBG"]["classification"], "diabetes_range")


if __name__ == "__main__":
    unittest.main()
