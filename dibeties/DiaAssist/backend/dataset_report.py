"""Dataset preparation + pre-processing demonstration (run this during the evaluation).

Steps shown:
  1. Dataset inventory      - every knowledge-base document: type, size, words
  2. Pre-processing         - raw vs cleaned text (ligatures, hyphenation, page numbers, repeated headers)
  3. Chunking               - chunk size/overlap, number of chunks, length statistics
  4. Processed dataset      - writes data/processed/*.txt, chunks.jsonl and summary.json
  5. Lab-report dataset     - 40 labelled synthetic reports (no patient data) and extraction accuracy

    python dataset_report.py
"""
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from src import documents  # noqa: E402
from src.preprocess import clean_with_stats  # noqa: E402

PROCESSED = os.path.join(ROOT, "data", "processed")


def bar(title):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


def main():
    os.makedirs(PROCESSED, exist_ok=True)
    names = [n for n in sorted(os.listdir(config.RAW_DOCS_DIR))
             if n.lower() != "readme.md" and os.path.splitext(n)[1].lower() in config.SUPPORTED_EXTENSIONS]

    bar("1. DATASET INVENTORY")
    raw = {}
    for n in names:
        path = os.path.join(config.RAW_DOCS_DIR, n)
        try:
            raw[n] = documents.extract_file(path, clean=False)
        except ValueError as exc:
            print(f"  skipped {n}: {exc}")
            continue
        print(f"  {n:50s} {os.path.getsize(path) / 1024:8.1f} KB  {len(raw[n].split()):7d} words")
    if not raw:
        sys.exit("No documents found. Put ADA/WHO files in data/knowledge_base_docs/ first.")
    print(f"  -> {len(raw)} documents, {sum(len(t.split()) for t in raw.values())} words")

    bar("2. PRE-PROCESSING (raw -> cleaned)")
    cleaned, summary_docs = {}, []
    for n, text in raw.items():
        c, st = clean_with_stats(text)
        cleaned[n] = c
        summary_docs.append({"source": n, **st})
        print(f"  {n:40s} {st['chars_before']:8d} -> {st['chars_after']:8d} chars | hyphen fixes {st['hyphenation_fixed']:3d} | "
              f"page numbers {st['page_number_lines_removed']:3d} | headers/footers {st['repeated_header_footer_lines_removed']:3d} | "
              f"references {st['reference_chars_removed'] // 1000:3d}k chars")
        with open(os.path.join(PROCESSED, os.path.splitext(n)[0] + ".txt"), "w", encoding="utf-8") as f:
            f.write(c)
    first = next(iter(raw))
    print(f"\n  Example ({first}), first 300 characters:")
    print("   RAW    :", repr(raw[first][:300]))
    print("   CLEANED:", repr(cleaned[first][:300]))

    bar("3. CHUNKING")
    from evaluation.retrieval_eval import chunk
    chunks = chunk([{"source": n, "text": t} for n, t in cleaned.items()], config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    lens = [len(c["content"]) for c in chunks]
    stats = {"chunk_size": config.CHUNK_SIZE, "overlap": config.CHUNK_OVERLAP, "chunks": len(chunks),
             "min_chars": min(lens), "median_chars": int(statistics.median(lens)), "max_chars": max(lens)}
    print("  ", stats)
    per_doc = {}
    for c in chunks:
        per_doc[c["source"]] = per_doc.get(c["source"], 0) + 1
    for n, k in per_doc.items():
        print(f"   {n:50s} {k:5d} chunks")
    with open(os.path.join(PROCESSED, "chunks.jsonl"), "w", encoding="utf-8") as f:
        for i, c in enumerate(chunks):
            f.write(json.dumps({"id": i, **c}, ensure_ascii=False) + "\n")

    bar("4. LAB-REPORT DATASET (labelled, synthetic)")
    from evaluation import make_lab_dataset, extraction_eval
    make_lab_dataset.main()
    m = extraction_eval.evaluate()
    print(f"  reports: {m['reports']}   labelled values: {m['values']}")
    print(f"  extraction recall {m['recall']:.1%} | precision {m['precision']:.1%} | classification accuracy {m['classification_accuracy']:.1%}")

    with open(os.path.join(PROCESSED, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"documents": summary_docs, "chunking": stats,
                   "lab_extraction": {k: v for k, v in m.items() if k not in ("per_parameter", "errors")}}, f, indent=1)
    bar("DONE")
    print(f"  Processed dataset saved in {PROCESSED}")
    print("  Next: python ingest.py (train the embedding index), then python evaluation/retrieval_eval.py")


if __name__ == "__main__":
    main()
