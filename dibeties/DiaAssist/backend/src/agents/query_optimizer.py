"""Query Optimizer Agent: rewrites the raw user question for better retrieval."""
import re

from src import llm_client

SYSTEM_PROMPT = """You are the Query Optimizer Agent in a diabetes clinical decision support system.
Rewrite the user's question into a clear, specific, retrieval-friendly query.
Rules:
- Keep standard medical abbreviations as-is (HbA1c, FBG, RBG, OGTT, LDL, HDL).
- Fix grammar, spelling, and ambiguity.
- Do not change the medical meaning or add new clinical claims.
- Return ONLY the rewritten query text, nothing else."""

_PREFIX = re.compile(r"^\s*(?:here(?:'s| is)[^:\n]*:|rewritten query:|query:)\s*", re.I)


def _clean(text: str, raw_query: str) -> str:
    """Small models often add 'Here is the rewritten query:' or quotes. Strip them, and fall back
    to the user's own wording if the rewrite is empty, multi-line or far longer than the question."""
    text = _PREFIX.sub("", (text or "").strip()).strip().strip('"').strip("'").strip()
    if not text or "\n" in text or len(text) > max(200, 3 * len(raw_query)):
        return raw_query
    return text


def optimize(raw_query: str) -> str:
    prompt = f"Original query: {raw_query}\n\nRewritten query:"
    try:
        result = llm_client.generate(prompt, system_instruction=SYSTEM_PROMPT, temperature=0.1)
    except llm_client.LLMError:
        return raw_query  # the answer step will report the real LLM problem
    return _clean(result, raw_query)
