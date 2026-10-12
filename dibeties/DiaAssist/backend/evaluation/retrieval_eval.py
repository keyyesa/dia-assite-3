"""Baseline vs. trained retrieval model - runs WITHOUT the LLM, so it is fast and repeatable.

  * Baseline model : TF-IDF + cosine similarity (classic lexical retrieval, numpy only).
  * BM25           : keyword search (a stronger lexical baseline, numpy/pure Python).
  * Trained model  : dense sentence embeddings (all-MiniLM-L6-v2) + cosine similarity (what the app's FAISS index uses).
  * Hybrid         : dense + BM25 merged with reciprocal-rank fusion (what the assistant uses by default).

Both are scored on the labelled questions in evaluation/test_questions.json. A retrieved chunk is
"relevant" when it contains at least half of the question's expected keywords.
Metrics: Hit@k, MRR, mean keyword recall of the top-k text.   Also compares chunk sizes (a small
hyper-parameter experiment).   Results are written to evaluation/retrieval_results.json.

    python evaluation/retrieval_eval.py              # baseline + dense, chunk sizes 400/800/1200
    python evaluation/retrieval_eval.py --no-dense   # baseline only (no model download)
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

import config  # noqa: E402
from src import documents  # noqa: E402
from src.preprocess import clean_text  # noqa: E402
from src.keyword_search import Bm25, reciprocal_rank_fusion  # noqa: E402

QUESTIONS = os.path.join(ROOT, "evaluation", "test_questions.json")
OUT = os.path.join(ROOT, "evaluation", "retrieval_results.json")
OUT_MD = os.path.join(ROOT, "evaluation", "retrieval_results.md")
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def load_docs():
    docs = []
    for name in sorted(os.listdir(config.RAW_DOCS_DIR)):
        if name.lower() == "readme.md" or os.path.splitext(name)[1].lower() not in config.SUPPORTED_EXTENSIONS:
            continue
        try:
            text = documents.extract_file(os.path.join(config.RAW_DOCS_DIR, name))
        except ValueError:
            continue
        if text.strip():
            docs.append({"source": name, "text": text})
    return docs


def chunk(docs, size, overlap):
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        sp = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", " ", ""])
        split = sp.split_text
    except ImportError:  # minimal fallback so the script still runs
        def split(t):
            step = max(size - overlap, 1)
            return [t[i:i + size] for i in range(0, len(t), step)]
    return [{"source": d["source"], "content": p.strip()} for d in docs for p in split(d["text"]) if p.strip()]


class TfidfRetriever:
    """Baseline model: sublinear TF-IDF vectors, cosine similarity."""
    def __init__(self, chunks):
        toks = [_TOKEN.findall(c["content"].lower()) for c in chunks]
        df = Counter(t for ts in toks for t in set(ts))
        self.vocab = {t: i for i, t in enumerate(df)}
        n = len(chunks)
        self.idf = np.array([math.log((1 + n) / (1 + df[t])) + 1 for t in self.vocab])
        self.matrix = np.vstack([self._vec(ts) for ts in toks]) if toks else np.zeros((0, len(self.vocab)))

    def _vec(self, tokens):
        v = np.zeros(len(self.vocab))
        for t, c in Counter(tokens).items():
            i = self.vocab.get(t)
            if i is not None:
                v[i] = (1 + math.log(c)) * self.idf[i]
        n = np.linalg.norm(v)
        return v / n if n else v

    def search(self, query, k):
        scores = self.matrix @ self._vec(_TOKEN.findall(query.lower()))
        return list(np.argsort(-scores)[:k])


class DenseRetriever:
    """Trained model: sentence-embedding vectors, cosine similarity."""
    def __init__(self, chunks, embedder):
        self.embedder = embedder
        emb = np.asarray(embedder.encode([c["content"] for c in chunks], convert_to_numpy=True, batch_size=32), dtype="float32")
        self.matrix = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9)

    def search(self, query, k):
        q = np.asarray(self.embedder.encode([query], convert_to_numpy=True), dtype="float32")[0]
        q = q / max(np.linalg.norm(q), 1e-9)
        return list(np.argsort(-(self.matrix @ q))[:k])


class Bm25Retriever:
    """Keyword baseline: Okapi BM25."""
    def __init__(self, chunks):
        self.bm = Bm25([c["content"] for c in chunks])

    def search(self, query, k):
        return [i for i, _ in self.bm.search(query, k)]


class HybridRetriever:
    """Dense + BM25, merged by reciprocal-rank fusion (same recipe as KnowledgeBase.search)."""
    def __init__(self, dense, bm25):
        self.dense, self.bm25 = dense, bm25

    def search(self, query, k):
        pool = max(k * 5, 20)
        fused = reciprocal_rank_fusion([list(self.dense.search(query, pool)), self.bm25.search(query, pool)])
        return [i for i, _ in fused[:k]]


def recall_of(text, keywords):
    t = text.lower()
    return sum(1 for k in keywords if k.lower() in t) / max(len(keywords), 1)


def score(retriever, chunks, questions, k):
    hits, rr, rec = [], [], []
    for q in questions:
        idx = retriever.search(q["question"], k)
        texts = [chunks[i]["content"] for i in idx]
        rel = [recall_of(t, q["expected_keywords"]) >= 0.5 for t in texts]
        hits.append(any(rel))
        rr.append(next((1 / (r + 1) for r, ok in enumerate(rel) if ok), 0.0))
        rec.append(recall_of(" ".join(texts), q["expected_keywords"]))
    return {"hit@k": round(float(np.mean(hits)), 3), "mrr": round(float(np.mean(rr)), 3), "keyword_recall": round(float(np.mean(rec)), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-dense", action="store_true")
    ap.add_argument("--k", type=int, default=config.TOP_K)
    ap.add_argument("--sizes", default="400,800,1200")
    a = ap.parse_args()
    docs = load_docs()
    if not docs:
        sys.exit("No documents found in " + config.RAW_DOCS_DIR)
    with open(QUESTIONS, encoding="utf-8") as f:
        questions = json.load(f)
    embedder = None
    if not a.no_dense:
        from src import vectorstore
        embedder = vectorstore.get_embedder()
    results = []
    print(f"{len(docs)} documents, {len(questions)} labelled questions, top-{a.k}\n")
    print(f"{'model':8s} {'chunk':>5s} {'chunks':>6s} {'Hit@k':>7s} {'MRR':>7s} {'recall':>7s}")
    for size in [int(s) for s in a.sizes.split(",")]:
        chunks = chunk(docs, size, min(config.CHUNK_OVERLAP, size // 4))
        bm25 = Bm25Retriever(chunks)
        models = [("TF-IDF", TfidfRetriever(chunks)), ("BM25", bm25)]
        if embedder is not None:
            dense = DenseRetriever(chunks, embedder)
            models += [("dense", dense), ("hybrid", HybridRetriever(dense, bm25))]
        for name, r in models:
            m = score(r, chunks, questions, a.k)
            results.append({"model": name, "chunk_size": size, "n_chunks": len(chunks), **m})
            print(f"{name:8s} {size:5d} {len(chunks):6d} {m['hit@k']:7.2f} {m['mrr']:7.2f} {m['keyword_recall']:7.2f}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"k": a.k, "questions": len(questions), "results": results}, f, indent=1)
    with open(OUT_MD, "w", encoding="utf-8") as f:  # a ready-made table for the report
        f.write(f"| Model | Chunk size | Chunks | Hit@{a.k} | MRR | Keyword recall |\n|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['model']} | {r['chunk_size']} | {r['n_chunks']} | {r['hit@k']:.2f} | {r['mrr']:.2f} | {r['keyword_recall']:.2f} |\n")
    print(f"\nSaved to {OUT} and {OUT_MD}")
    print("Note: scores depend on the documents in data/knowledge_base_docs - add the real ADA/WHO files for meaningful numbers.")


if __name__ == "__main__":
    main()
