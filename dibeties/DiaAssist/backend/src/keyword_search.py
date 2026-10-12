"""Keyword search (BM25) and rank fusion, used together with the FAISS vector search ("hybrid retrieval").

Why both?  Dense embeddings find passages that *mean* the same thing but can miss exact terms such as
"eGFR", "U-100" or "6.5"; BM25 finds exact terms but not paraphrases. Reciprocal-rank fusion (RRF) merges the
two ranked lists, so a passage that is high in either list (and best, in both) comes first.

Pure Python + numpy only, so it can be tested without the embedding model.
"""
import math
import re
from collections import Counter, defaultdict

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOP = frozenset("""a an and are as at be by do does for from how in is it of on or the this that to was were what when
which who why with can should would about into than then there their they your you i""".split())


def tokenize(text: str) -> list:
    return [t for t in _TOKEN.findall((text or "").lower()) if t not in _STOP]


class Bm25:
    """Okapi BM25 over a list of texts (an inverted index, so a query only touches the chunks that contain its terms)."""

    def __init__(self, texts, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(texts)
        self.postings = defaultdict(list)  # term -> [(doc, term frequency)]
        self.lengths = []
        for i, text in enumerate(texts):
            toks = tokenize(text)
            self.lengths.append(len(toks))
            for term, tf in Counter(toks).items():
                self.postings[term].append((i, tf))
        self.avg_len = (sum(self.lengths) / self.n) if self.n else 0.0

    def _idf(self, term: str) -> float:
        df = len(self.postings.get(term, ()))
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 10) -> list:
        """[(doc_index, score)] best first; chunks that share no term with the query are not returned."""
        scores = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self._idf(term)
            for doc, tf in self.postings.get(term, ()):
                norm = 1 - self.b + self.b * self.lengths[doc] / (self.avg_len or 1.0)
                scores[doc] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


def reciprocal_rank_fusion(rankings, k0: int = 60) -> list:
    """Merge several ranked lists of ids. Returns [(id, fused_score)] best first (ties keep first-list order)."""
    fused, first_seen = defaultdict(float), {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            fused[item] += 1.0 / (k0 + rank + 1)
            first_seen.setdefault(item, len(first_seen))
    return sorted(fused.items(), key=lambda kv: (-kv[1], first_seen[kv[0]]))
