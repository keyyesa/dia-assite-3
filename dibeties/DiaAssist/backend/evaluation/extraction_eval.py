"""Measures the report-analysis agent on the labelled synthetic lab reports (rules only, no LLM needed).

Metrics: extraction recall / precision (value within 3 % of the truth), classification accuracy on the
extracted values, and a per-parameter breakdown.   python evaluation/extraction_eval.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.agents.report_analysis import extract_values_by_rules, REFERENCE_BANDS, convert_to_canonical, classify_value, _appears_in_text, _split_value_unit  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab_reports.json")


def interpret_rules_only(text: str) -> dict:
    out = {}
    for p, item in extract_values_by_rules(text).items():
        value, unit = _split_value_unit(item)
        if value is None or not _appears_in_text(value, text):
            continue
        conv = convert_to_canonical(p, value, unit)
        if conv is not None:
            out[p] = {"value": conv, "classification": classify_value(p, conv)}
    return out


def evaluate(path=DATA) -> dict:
    if not os.path.exists(path):  # first run: build the labelled synthetic reports automatically
        from evaluation.make_lab_dataset import main as make_dataset
        make_dataset()
    with open(path, encoding="utf-8") as f:
        reports = json.load(f)
    tp = fp = fn = cls_ok = 0
    per = {}
    errors = []
    for r in reports:
        got = interpret_rules_only(r["text"])
        for p, t in r["truth"].items():
            s = per.setdefault(p, {"n": 0, "found": 0, "class_ok": 0})
            s["n"] += 1
            g = got.get(p)
            if g and abs(g["value"] - t["value"]) <= max(0.03 * abs(t["value"]), 0.15):
                tp += 1; s["found"] += 1
                if g["classification"] == t["class"]:
                    cls_ok += 1; s["class_ok"] += 1
                else:
                    errors.append((r["id"], p, t["value"], g["classification"], t["class"]))
            else:
                fn += 1
                errors.append((r["id"], p, t["value"], g and g["value"], "missed/wrong value"))
        fp += sum(1 for p in got if p not in r["truth"])
    return {"reports": len(reports), "values": tp + fn, "recall": tp / max(tp + fn, 1), "precision": tp / max(tp + fp, 1),
            "classification_accuracy": cls_ok / max(tp, 1), "per_parameter": per, "errors": errors}


if __name__ == "__main__":
    m = evaluate()
    print(f"Reports: {m['reports']}   labelled values: {m['values']}")
    print(f"Extraction recall:    {m['recall']:.1%}\nExtraction precision: {m['precision']:.1%}\nClassification accuracy: {m['classification_accuracy']:.1%}")
    for p, s in m["per_parameter"].items():
        print(f"  {p:18s} found {s['found']}/{s['n']}   class ok {s['class_ok']}/{s['found'] or 1}")
    for e in m["errors"][:15]:
        print("  miss:", e)
