import importlib.util
import unittest

import numpy as np

from src.keyword_search import Bm25, reciprocal_rank_fusion, tokenize

TEXTS = [
    "Metformin is the usual first medicine for type 2 diabetes unless kidney function is very low.",
    "An eGFR below 30 mL/min/1.73 m2 means metformin should not be started.",
    "A1C of 6.5% or higher on two tests confirms the diagnosis of diabetes.",
    "Regular walking and strength training improve blood glucose control.",
    "U-100 vial and U-100 prefilled pen are the common insulin presentations.",
]


class Bm25Tests(unittest.TestCase):
    def setUp(self):
        self.bm = Bm25(TEXTS)

    def test_exact_term_is_found(self):
        self.assertEqual(self.bm.search("eGFR")[0][0], 1)
        self.assertEqual(self.bm.search("U-100 pen")[0][0], 4)

    def test_number_token_is_kept(self):
        self.assertIn("6.5", tokenize("A1C 6.5% or higher"))
        self.assertEqual(self.bm.search("6.5 diagnosis")[0][0], 2)

    def test_no_shared_term_returns_nothing(self):
        self.assertEqual(self.bm.search("xylophone"), [])

    def test_stop_words_do_not_match(self):
        self.assertEqual(self.bm.search("the of and"), [])

    def test_empty_index(self):
        self.assertEqual(Bm25([]).search("anything"), [])


class FusionTests(unittest.TestCase):
    def test_item_in_both_lists_wins(self):
        fused = reciprocal_rank_fusion([[3, 1, 2], [2, 3, 9]])
        self.assertEqual([i for i, _ in fused][:2], [3, 2])
        self.assertEqual(len(fused), 4)

    def test_single_list_keeps_order(self):
        self.assertEqual([i for i, _ in reciprocal_rank_fusion([[5, 4, 3]])], [5, 4, 3])

    def test_empty(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])


class _FakeEmbedder:
    """Bag-of-words vectors: enough to exercise KnowledgeBase.search without the real model."""
    VOCAB = ["metformin", "kidney", "walking", "diagnosis", "insulin", "egfr", "glucose", "pen"]

    def encode(self, texts, convert_to_numpy=True, **_):
        return np.array([[float(w in t.lower()) for w in self.VOCAB] for t in texts], dtype="float32") + 1e-3


@unittest.skipUnless(importlib.util.find_spec("faiss"), "faiss is not installed")
class KnowledgeBaseHybridTests(unittest.TestCase):
    def setUp(self):
        import faiss
        from src.vectorstore import KnowledgeBase
        self.faiss = faiss
        emb = _FakeEmbedder()
        matrix = np.asarray(emb.encode(TEXTS), dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        kb = KnowledgeBase.__new__(KnowledgeBase)
        kb.index, kb.embedder = index, emb
        kb.chunks = [{"source": f"doc{i}", "content": t} for i, t in enumerate(TEXTS)]
        self.kb = kb

    def test_every_result_has_a_cosine_score(self):
        for hybrid in (False, True):
            res = self.kb.search("metformin kidney", k=3, hybrid=hybrid)
            self.assertEqual(len(res), 3)
            self.assertTrue(all(-1.0 <= r["score"] <= 1.0001 for r in res))

    def test_hybrid_returns_k_unique_chunks(self):
        res = self.kb.search("egfr metformin", k=4, hybrid=True)
        self.assertEqual(len({r["source"] for r in res}), len(res))
        self.assertLessEqual(len(res), 4)

    def test_dense_only_mode_still_works(self):
        res = self.kb.search("walking", k=2, hybrid=False)
        self.assertEqual(res[0]["source"], "doc3")


if __name__ == "__main__":
    unittest.main()
