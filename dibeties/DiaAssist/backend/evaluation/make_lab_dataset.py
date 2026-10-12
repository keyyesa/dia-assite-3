"""Builds a labelled synthetic dataset of lab reports (no patient data) to measure report extraction.

Each report has a randomly chosen layout, a random subset of tests, and sometimes SI units
(mmol/L, mmol/mol). The *target class* is chosen first and the value sampled inside that class, so
the ground-truth label never depends on the code under test.

    python evaluation/make_lab_dataset.py          # writes evaluation/lab_reports.json (seeded)
"""
import json
import os
import random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab_reports.json")

# parameter -> (printed label variants, canonical unit, {class: (low, high)}) with a safety gap at every cut-off
SPEC = {
    "HbA1c": (["HbA1c", "Glycated Haemoglobin (HbA1c)", "A1c"], "%",
              {"normal": (4.5, 5.6), "prediabetes_range": (5.8, 6.4), "diabetes_range": (6.7, 12.0)}),
    "FBG": (["Fasting Blood Glucose (FBG)", "Fasting Glucose", "FBS"], "mg/dL",
            {"normal": (76, 98), "prediabetes_range": (103, 123), "diabetes_range": (130, 300)}),
    "RBG": (["Random Blood Glucose (RBG)", "Random Glucose", "RBS"], "mg/dL",
            {"below_diagnostic_threshold": (76, 195), "diabetes_range_if_symptomatic": (206, 400)}),
    "Serum_Creatinine": (["Serum Creatinine", "Creatinine"], "mg/dL", {"normal": (0.6, 1.2), "elevated": (1.5, 4.0)}),
    "Urine_Albumin": (["Urine Albumin", "Urine Albumin/Creatinine Ratio (UACR)"], "mg/g",
                      {"normal": (5, 27), "microalbuminuria": (35, 280), "macroalbuminuria": (320, 1000)}),
    "LDL": (["LDL Cholesterol", "LDL-C", "LDL"], "mg/dL", {"optimal": (60, 94), "borderline": (106, 154), "high": (166, 250)}),
    "HDL": (["HDL Cholesterol", "HDL-C", "HDL"], "mg/dL", {"low": (25, 37), "acceptable": (45, 80)}),
    "Triglycerides": (["Triglycerides", "TG"], "mg/dL", {"normal": (70, 145), "borderline": (156, 194), "high": (210, 480)}),
}
SI = {  # alternative unit -> (name, factor from canonical value, decimals)
    "HbA1c": ("mmol/mol", lambda v: (v - 2.15) * 10.929, 0),
    "FBG": ("mmol/L", lambda v: v / 18.016, 1), "RBG": ("mmol/L", lambda v: v / 18.016, 1),
    "Serum_Creatinine": ("umol/L", lambda v: v * 88.4, 0),
    "LDL": ("mmol/L", lambda v: v / 38.67, 2), "HDL": ("mmol/L", lambda v: v / 38.67, 2),
    "Triglycerides": ("mmol/L", lambda v: v / 88.57, 2),
}
REF = {"HbA1c": "4.0 - 5.6", "FBG": "70 - 99", "RBG": "< 140", "Serum_Creatinine": "0.6 - 1.3", "Urine_Albumin": "< 30",
       "LDL": "< 100", "HDL": "> 40", "Triglycerides": "< 150"}


def _fmt(v, decimals):
    return f"{v:.{decimals}f}" if decimals else str(int(round(v)))


def make_report(rng: random.Random, idx: int) -> dict:
    params = rng.sample(list(SPEC), k=rng.randint(4, len(SPEC)))
    layout = rng.choice(["colon", "spaces", "table", "ref"])
    use_si = rng.random() < 0.35
    lines = [f"Laboratory Report - Sample {idx:03d}", f"Date: 2026-0{rng.randint(1, 9)}-{rng.randint(10, 28)}", ""]
    truth = {}
    for p in params:
        labels, unit, classes = SPEC[p]
        cls = rng.choice(list(classes))
        lo, hi = classes[cls]
        value = round(rng.uniform(lo, hi), 1 if hi < 20 else 0)
        printed_v, printed_u, dec = value, unit, 1 if p in ("HbA1c", "Serum_Creatinine") else 0
        if use_si and p in SI:
            printed_u, conv, dec = SI[p]
            printed_v = conv(value)
        txt = _fmt(printed_v, dec if (use_si and p in SI) else (1 if isinstance(value, float) and value < 20 else 0))
        label = rng.choice(labels)
        row = {"colon": f"{label}: {txt} {printed_u}", "spaces": f"{label}    {txt} {printed_u}",
               "table": f"{label} | {txt} | {printed_u} | {REF[p]}", "ref": f"{label} {txt} {printed_u} (Ref: {REF[p]})"}[layout]
        lines.append(row)
        truth[p] = {"value": value, "class": cls}
    return {"id": idx, "text": "\n".join(lines), "truth": truth}


def main(n=40, seed=7):
    rng = random.Random(seed)
    data = [make_report(rng, i + 1) for i in range(n)]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"wrote {n} labelled reports to {OUT}")


if __name__ == "__main__":
    main()
