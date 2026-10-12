import unittest

from src.preprocess import clean_text, clean_with_stats, strip_references

BODY = "Glycemic goals are individualised. " * 60
REFS = "References\n" + "".join(
    f"{i}. Author A, Author B. Diabetes management. Diabetes Care 20{10 + i % 14};{40 + i}:{100 + i}-{110 + i}\n"
    for i in range(1, 40))


class StripReferencesTests(unittest.TestCase):
    def test_reference_list_is_removed(self):
        out, removed = strip_references(BODY + "\n" + REFS)
        self.assertGreater(removed, 500)
        self.assertNotIn("Author A", out)
        self.assertIn("Glycemic goals", out)

    def test_clean_with_stats_reports_it(self):
        text, stats = clean_with_stats(BODY + "\n" + REFS)
        self.assertGreater(stats["reference_chars_removed"], 500)
        self.assertNotIn("Diabetes Care 20", text)

    def test_heading_in_running_text_is_kept(self):
        # "References" near the top, or followed by prose without citations, must not truncate the document
        early = "References\nthis early heading is ignored.\n" + BODY
        self.assertEqual(strip_references(early)[1], 0)
        prose = BODY + "\nReferences\n" + "The patient should be reviewed every three months. " * 40
        self.assertEqual(strip_references(prose)[1], 0)

    def test_table_of_contents_entry_is_kept(self):
        toc = "Contents\nReferences.....................76\n" + BODY
        self.assertEqual(strip_references(toc)[1], 0)

    def test_no_references_no_change(self):
        self.assertEqual(clean_text(BODY).strip(), BODY.strip())


if __name__ == "__main__":
    unittest.main()


class RunningHeaderTests(unittest.TestCase):
    def _doc(self, pages=8):
        out = []
        for i in range(1, pages + 1):
            out.append(f"[Page {i}]\nDiabetes Care Volume 48, Supplement 1, January 2025\n"
                       + "".join(f"Body sentence {j} of page {i} about glycemic treatment choices.\n" for j in range(10))
                       + f"Metformin starting dose is low and increased slowly (item {i}).\n"
                       "U-100 vial\nInsulin glargine is a basal insulin used once daily in many people.\n"
                       + "".join(f"More body {j} of page {i} about insulin pens and vials.\n" for j in range(10))
                       + "diabetesjournals.org/care")
        return "\n".join(out)

    def test_header_and_footer_removed_but_table_label_kept(self):
        text = self._doc()
        text = text.replace("Metformin starting dose", "U-100 vial\nMetformin starting dose", 2)  # mid-page repeat
        out, stats = clean_with_stats(text)
        self.assertNotIn("January 2025", out)
        self.assertNotIn("diabetesjournals.org/care", out)
        self.assertIn("U-100 vial", out)
        self.assertGreaterEqual(stats["repeated_header_footer_lines_removed"], 16)

    def test_short_label_repeated_without_page_markers_is_kept(self):
        text = "\n".join(["Neutral", "Insulin is a hormone that lowers blood glucose in the body today"] * 6)
        self.assertIn("Neutral", clean_text(text))
