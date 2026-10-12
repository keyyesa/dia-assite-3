"""Text pre-processing applied to every knowledge-base document before chunking.

PDF text extracted from guidelines is noisy. These steps (all deterministic, no model needed) make
the chunks cleaner and the embeddings more reliable:

  1. normalise unicode (ligatures such as "ﬁ", non-breaking spaces, odd dashes/quotes);
  2. repair words hyphenated across line breaks ("gly-\\ncemic" -> "glycemic");
  3. drop page markers / bare page numbers and lines that repeat on many pages (running headers/footers);
  4. cut the reference list at the end of a paper (a quarter to a half of an ADA section is citations,
     which only add noise to retrieval);
  5. remove control characters and collapse runs of spaces and blank lines.

`clean_text(text)` returns the cleaned text; `clean_with_stats(text)` also returns what was removed.
"""
import re
import unicodedata
from collections import Counter

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", " ": " ", " ": " ",
              "​": "", "­": "", "–": "-", "—": "-", "‐": "-", "‑": "-", "“": '"', "”": '"',
              "‘": "'", "’": "'", "≥": ">=", "≤": "<="}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_PAGE_LINE = re.compile(r"^\s*(?:\[?\s*page\s*\d+(?:\s*(?:of|/)\s*\d+)?\s*\]?|-?\s*\d{1,4}\s*-?)\s*$", re.I)


_REF_HEADING = re.compile(r"^[ \t]*(?:references?|bibliography)[ \t]*:?[ \t]*$", re.I | re.M)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def strip_references(text: str):
    """Drop the trailing reference list. Returns (text, characters_removed).

    A standalone "References" heading is only treated as the start of the list when it sits after the first
    30 % of the text AND everything after it is citation-dense (>= 2 years per 100 words; running text has
    about 0.1-0.35, reference lists about 3.5-4.3). Anything else is left untouched.
    """
    for m in _REF_HEADING.finditer(text):
        if m.start() < 0.3 * len(text):
            continue
        rest = text[m.start():]
        words = max(1, len(rest.split()))
        if 100 * len(_YEAR.findall(rest)) / words >= 2.0:
            return text[: m.start()].rstrip(), len(rest)
    return text, 0


_PAGE_MARK = re.compile(r"^\[Page \d+\]\s*$", re.M)
_EDGE = 4  # a running header/footer sits within the first/last few lines of a page


def _repeated_lines(lines, min_repeats=4, max_len=90, min_len=25):
    """Fallback for text without page markers: long lines that repeat many times."""
    counts = Counter(l.strip() for l in lines if min_len <= len(l.strip()) <= max_len)
    return {l for l, n in counts.items() if n >= min_repeats and not l.endswith(".")}


def _edge_positions(page_lines):
    """Indexes of the first/last few non-empty lines of one page."""
    idx = [i for i, l in enumerate(page_lines) if l.strip()]
    return set(idx[:_EDGE] + idx[-_EDGE:])


def _drop_running_headers(t: str):
    """Remove running headers/footers. With page markers a line counts only when it sits at the top or
    bottom of at least a quarter of the pages, so table labels and headings that merely repeat survive.
    Returns (text, number_of_lines_removed)."""
    parts = _PAGE_MARK.split(t)
    if len(parts) < 5:  # fewer than 4 pages marked: use the length-based fallback
        lines = t.split("\n")
        rep = _repeated_lines(lines)
        kept = [l for l in lines if l.strip() not in rep]
        return "\n".join(kept), len(lines) - len(kept)
    pages = [p.split("\n") for p in parts]
    edges = [_edge_positions(p) for p in pages]
    counts = Counter()
    for pl, ed in zip(pages, edges):
        counts.update({pl[i].strip() for i in ed if 3 <= len(pl[i].strip()) <= 120})
    need = max(3, -(-len(pages) // 4))
    rep = {l for l, n in counts.items() if n >= need and not l.endswith(".")}
    removed, out = 0, []
    for pl, ed in zip(pages, edges):
        keep = []
        for i, line in enumerate(pl):
            if i in ed and line.strip() in rep:
                removed += 1
            else:
                keep.append(line)
        out.append("\n".join(keep))
    return "\n".join(out), removed


def clean_with_stats(text: str):
    original = text or ""
    t = unicodedata.normalize("NFKC", original)
    for bad, good in _LIGATURES.items():
        t = t.replace(bad, good)
    t = _CONTROL.sub("", t).replace("\r\n", "\n").replace("\r", "\n")
    before_hyphen = t
    t = _HYPHEN_BREAK.sub(r"\1\2", t)
    hyphen_fixes = len(_HYPHEN_BREAK.findall(before_hyphen))

    t, reference_chars = strip_references(t)
    t, header_lines = _drop_running_headers(t)

    lines = t.split("\n")
    kept, page_lines = [], 0
    for line in lines:
        s = line.strip()
        if s and _PAGE_LINE.match(s):
            page_lines += 1
            continue
        kept.append(re.sub(r"[ \t]+", " ", line).rstrip())
    t = "\n".join(kept)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    stats = {"chars_before": len(original), "chars_after": len(t), "hyphenation_fixed": hyphen_fixes,
             "page_number_lines_removed": page_lines, "repeated_header_footer_lines_removed": header_lines,
             "reference_chars_removed": reference_chars}
    return t, stats


def clean_text(text: str) -> str:
    return clean_with_stats(text)[0]
