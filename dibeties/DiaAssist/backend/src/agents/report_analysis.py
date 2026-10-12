"""
Report Analysis Agent: extracts diabetes-relevant lab values from a report's raw text and
classifies each value against standard reference ranges using a deterministic rule table
(so classification never depends on the LLM's arithmetic).

Extraction works in two layers:
  1. RULES (regular expressions): fast, offline, no LLM needed, and the numbers always come
     straight from the report text.
  2. LLM (optional): only used when the rules find fewer than MIN_RULE_HITS values, to catch
     unusual layouts. If the LLM is unreachable, the rule results are still returned and a
     warning explains what happened (errors are never silently turned into "no values found").

Safeguards:
  * values the LLM returns are dropped if the number does not actually appear in the report;
  * common unit variants (mmol/L, umol/L, mmol/mol, mg/mmol) are converted to the canonical unit;
  * ranges use exclusive upper bounds, so decimal values never fall into gaps.

Labels say "..._range" on purpose: a single lab value is not a diagnosis.
"""
import math
import re
from src import llm_client
from src.agents.json_utils import extract_json

INF = math.inf
MIN_RULE_HITS = 4

# Ordered bands per parameter: a value belongs to the first band whose (exclusive)
# upper bound is greater than the value.
REFERENCE_BANDS = {
    "HbA1c": {"unit": "%", "bands": [(4.0, "low"), (5.7, "normal"), (6.5, "prediabetes_range"), (INF, "diabetes_range")]},
    "FBG": {"unit": "mg/dL", "bands": [(70, "low"), (100, "normal"), (126, "prediabetes_range"), (INF, "diabetes_range")]},
    # Random glucose has no prediabetes category; >=200 mg/dL counts only together with classic symptoms.
    "RBG": {"unit": "mg/dL", "bands": [(70, "low"), (200, "below_diagnostic_threshold"), (INF, "diabetes_range_if_symptomatic")]},
    "OGTT_2hr": {"unit": "mg/dL", "bands": [(140, "normal"), (200, "prediabetes_range"), (INF, "diabetes_range")]},
    # Creatinine ranges differ by sex/lab: use the lab's own reference interval when available.
    "Serum_Creatinine": {"unit": "mg/dL", "bands": [(1.3, "normal"), (INF, "elevated")]},
    # ADA: UACR 30-299 mg/g moderately increased, >=300 mg/g severely increased.
    "Urine_Albumin": {"unit": "mg/g", "bands": [(30, "normal"), (300, "microalbuminuria"), (INF, "macroalbuminuria")]},
    "LDL": {"unit": "mg/dL", "bands": [(100, "optimal"), (160, "borderline"), (INF, "high")]},
    # HDL goal is sex-specific (men >=40, women >=50 mg/dL); 40 is used as the general cut-off.
    "HDL": {"unit": "mg/dL", "bands": [(40, "low"), (INF, "acceptable")]},
    "Triglycerides": {"unit": "mg/dL", "bands": [(150, "normal"), (200, "borderline"), (500, "high"), (INF, "very_high")]},
}


def _same(v):
    return v


_GLUCOSE = {"mg/dl": _same, "mmol/l": lambda v: v * 18.016}
_CHOL = {"mg/dl": _same, "mmol/l": lambda v: v * 38.67}

# unit (normalised: lowercase, no spaces) -> converter into the canonical unit
CONVERSIONS = {
    "HbA1c": {"%": _same, "mmol/mol": lambda v: v / 10.929 + 2.15},
    "FBG": _GLUCOSE,
    "RBG": _GLUCOSE,
    "OGTT_2hr": _GLUCOSE,
    "Serum_Creatinine": {"mg/dl": _same, "umol/l": lambda v: v / 88.4},
    "Urine_Albumin": {"mg/g": _same, "mg/gcreat": _same, "mg/gcr": _same, "ug/mg": _same,
                      "mg/mmol": lambda v: v * 8.84},
    "LDL": _CHOL,
    "HDL": _CHOL,
    "Triglycerides": {"mg/dl": _same, "mmol/l": lambda v: v * 88.57},
}

# --------------------------------------------------------------------------- rule-based extraction
_UNIT = (r"(%|mg\s*/\s*d[lL]|mmol\s*/\s*mol|mmol\s*/\s*[lL]|[uµμ]mol\s*/\s*[lL]|"
         r"mg\s*/\s*g(?:\s*creat\w*)?|mg\s*/\s*mmol|[uµμ]g\s*/\s*mg)")

# Order matters: the albumin/creatinine ratio must be tried before plain creatinine.
_LABELS = {
    "Urine_Albumin": r"(?:urine\s+albumin(?:\s*(?:/|to)\s*creatinine(?:\s+ratio)?)?|albumin\s*/\s*creatinine(?:\s+ratio)?"
                     r"|\buacr\b|\bacr\b|micro\s*albumin(?:uria)?)",
    "HbA1c": r"(?:hb\s*a1c|\ba1c\b|gly[ck]\w*\s+h(?:a)?emoglobin)",
    "FBG": r"(?:fasting\s+(?:blood\s+)?(?:glucose|sugar)(?:\s*\(?\s*fb[gs]\s*\)?)?|\bfb[gs]\b)",
    "RBG": r"(?:random\s+(?:blood\s+)?(?:glucose|sugar)(?:\s*\(?\s*rb[gs]\s*\)?)?|\brb[gs]\b)",
    "OGTT_2hr": r"(?:\bogtt\b[^\n\d]{0,25}|2[\s-]*h(?:ou)?rs?\s+(?:post[\s-]*(?:load|prandial)\s+)?glucose|post[\s-]*prandial\s+glucose)",
    "Serum_Creatinine": r"(?<!/)(?<!/\s)(?<!to\s)(?:serum\s+)?creatinine(?!\s*(?:ratio|clearance))",
    "LDL": r"(?:\bldl(?:[\s-]*c(?:holesterol)?)?\b|ldl\s+cholesterol)",
    "HDL": r"(?<!non-)(?<!non\s)(?:\bhdl(?:[\s-]*c(?:holesterol)?)?\b|hdl\s+cholesterol)",
    "Triglycerides": r"(?:triglycerides?|\btg\b)",
}
_NUMBER_AFTER = re.compile(r"(?:\s*\([^)\n]{0,20}\))?[^0-9\n]{0,40}?(\d+(?:[.,]\d+)?)\s*(?:[|\t]\s*)?(?:" + _UNIT + r")?", re.I)
_COMPILED = {k: re.compile(v, re.I) for k, v in _LABELS.items()}


def extract_values_by_rules(report_text: str) -> dict:
    """{param: {"value": float, "unit": str|None}} read straight from the text (first mention wins)."""
    found = {}
    for param, label in _COMPILED.items():
        for m in label.finditer(report_text):
            tail = _NUMBER_AFTER.match(report_text, m.end())
            if not tail:
                continue
            try:
                value = float(tail.group(1).replace(",", "."))
            except ValueError:
                continue
            unit = re.sub(r"\s+", "", tail.group(2)) if tail.group(2) else None
            found[param] = {"value": value, "unit": unit}
            break
    return found


EXTRACTION_SYSTEM_PROMPT = """You are the Report Analysis Agent for diabetes laboratory reports.
Extract these parameters if present in the report text:
HbA1c, FBG, RBG, OGTT_2hr, Serum_Creatinine, Urine_Albumin, LDL, HDL, Triglycerides
Return a flat JSON object where each key maps to {"value": <number>, "unit": "<unit exactly as printed in the report, or null>"}.
Copy numbers exactly as printed. Never estimate, infer or calculate a value that is not printed.
Omit any parameter that is not present. Return ONLY valid JSON, no markdown fences, no explanation."""


def _norm_unit(unit):
    if not unit:
        return None
    return str(unit).strip().lower().replace(" ", "").replace("µ", "u").replace("μ", "u")


def _appears_in_text(value: float, text: str) -> bool:
    """True if the number is literally present in the report text (hallucination guard)."""
    candidates = {f"{value:g}", f"{value:.1f}", f"{value:.2f}"}
    candidates |= {c.replace(".", ",") for c in candidates}
    for c in candidates:
        if re.search(rf"(?<![\d.,]){re.escape(c)}(?!\d|[.,]\d)", text):
            return True
    return False


def _split_value_unit(raw):
    """Accepts {"value": 7.2, "unit": "%"} or a bare number/string. Returns (float|None, unit|None)."""
    unit = None
    if isinstance(raw, dict):
        unit = raw.get("unit")
        raw = raw.get("value")
    try:
        return float(str(raw).replace(",", ".").strip().rstrip("%")), unit
    except (TypeError, ValueError):
        return None, unit


def convert_to_canonical(param: str, value: float, unit):
    """Returns the value in the canonical unit, or None if the unit is not supported."""
    unit_n = _norm_unit(unit)
    if unit_n is None:
        return value  # no unit printed: assume the canonical unit
    converter = CONVERSIONS.get(param, {}).get(unit_n)
    return converter(value) if converter else None


# Plain-language notes shown next to values whose "range" is a general convention, not an ADA target.
CLASSIFICATION_NOTES = {
    "LDL": ("General range only. The ADA sets an LDL goal by cardiovascular risk (for example below 70 mg/dL, or "
            "below 55 mg/dL with existing heart disease), so your doctor decides your own target."),
    "HDL": ("The ADA treats HDL below 40 mg/dL as low. Doctors may use a higher goal for women, "
            "so ask your doctor what is right for you."),
    "Triglycerides": ("The ADA treats fasting triglycerides above 150 mg/dL as raised. "
                      "Your doctor decides whether treatment is needed."),
}


def classify_value(param: str, value: float) -> str:
    spec = REFERENCE_BANDS.get(param)
    if not spec:
        return "unknown"
    for upper, label in spec["bands"]:
        if value < upper:
            return label
    return spec["bands"][-1][1]


def extract_values(report_text: str) -> dict:
    """LLM extraction. Raises llm_client.LLMError if the model cannot be reached."""
    result = llm_client.generate(report_text, system_instruction=EXTRACTION_SYSTEM_PROMPT, temperature=0.0)
    return extract_json(result)


def analyze_report_detailed(report_text: str) -> dict:
    """{'values': {...}, 'method': 'rules'|'rules+llm'|'llm'|'none', 'warning': str|None}"""
    raw = extract_values_by_rules(report_text)
    method, warning = "rules", None
    if len(raw) < MIN_RULE_HITS:
        try:
            for param, item in extract_values(report_text).items():
                raw.setdefault(param, item)
            method = "rules+llm" if raw else "llm"
        except Exception as exc:  # noqa: BLE001 - keep the rule results, but tell the user why the LLM was skipped
            warning = ("The language model could not be reached, so only values found by pattern matching are shown. "
                       f"Details: {str(exc).splitlines()[0][:200]}")
    if not raw:
        method = "none"

    interpretation = {}
    for param, item in raw.items():
        if param not in REFERENCE_BANDS:
            continue
        value, unit = _split_value_unit(item)
        if value is None or not _appears_in_text(value, report_text):
            continue  # missing, unparseable, or not actually printed in the report
        canonical_unit = REFERENCE_BANDS[param]["unit"]
        converted = convert_to_canonical(param, value, unit)
        if converted is None:
            interpretation[param] = {"value": value, "unit": unit, "classification": "unit_not_supported"}
            continue
        entry = {
            "value": round(converted, 2),
            "unit": canonical_unit,
            "classification": classify_value(param, converted),
        }
        if param in CLASSIFICATION_NOTES:
            entry["note"] = CLASSIFICATION_NOTES[param]
        if _norm_unit(unit) not in (None, _norm_unit(canonical_unit)):
            entry["reported_as"] = f"{value:g} {unit}"
        interpretation[param] = entry
    return {"values": interpretation, "method": method if interpretation else "none", "warning": warning}


def analyze_report(report_text: str) -> dict:
    """Returns {param: {value, unit, classification[, reported_as]}} for every trustworthy parameter."""
    return analyze_report_detailed(report_text)["values"]
