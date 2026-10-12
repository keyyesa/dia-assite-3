"""Response Generation Agent: produces the final answer from retrieved context."""
from src import llm_client

SYSTEM_PROMPT = """You are the Response Generation Agent for DiaAssist AI, a diabetes clinical
decision support system.
Generate a clear, structured, evidence-based answer using ONLY the provided context
(retrieved guideline excerpts and/or lab report interpretation).
Rules:
- Cite sources inline like [Source: <source_name>] right after any claim drawn from the context.
- If lab report interpretation is provided, incorporate it and clearly flag any abnormal values.
  When a value has a "Note", repeat that note in plain words: those ranges are general, and the doctor
  sets the personal target.
- Do not invent facts that are not present in the context. If the context is insufficient to
  answer fully, say so explicitly.
- Use the earlier conversation only to understand what the user is referring to ("it", "that",
  "those values"); the facts must still come from the context.
- Write in clear prose paragraphs, avoid unnecessary jargon.
- Always end with a short disclaimer that this is decision support only and does not replace
  the judgment of a qualified healthcare professional."""

HISTORY_TURNS = 6  # last 3 question/answer pairs are enough to resolve a follow-up


def _history_block(history) -> str:
    if not history:
        return ""
    lines = []
    for m in history[-HISTORY_TURNS:]:
        who = "User" if m.get("role") == "user" else "Assistant"
        text = " ".join(str(m.get("content", "")).split())
        lines.append(f"{who}: {text[:600]}")
    return "Earlier conversation:\n" + "\n".join(lines) + "\n\n"


def generate_response(query: str, retrieved_chunks: list, report_interpretation: dict = None,
                      on_token=None, history: list = None) -> str:
    """on_token(piece) is called for every streamed piece of text (optional).
    history: earlier [{'role': 'user'|'assistant', 'content': str}] messages (optional)."""
    context_parts = [f"[Source: {c['source']}]\n{c['content']}" for c in retrieved_chunks]
    context_text = "\n\n".join(context_parts) if context_parts else "No guideline context was retrieved."

    report_text = ""
    if report_interpretation:
        lines = [
            f"- {param}: {info['value']} {info.get('unit') or ''} -> {info['classification']}"
            + (f" (Note: {info['note']})" if info.get("note") else "")
            for param, info in report_interpretation.items()
        ]
        report_text = "Lab Report Interpretation:\n" + "\n".join(lines)

    prompt = f"""{_history_block(history)}User query: {query}

Retrieved guideline context:
{context_text}

{report_text}

Generate the response now."""

    if on_token is None:
        return llm_client.generate(prompt, system_instruction=SYSTEM_PROMPT, temperature=0.3)

    pieces = []
    for piece in llm_client.generate_stream(prompt, system_instruction=SYSTEM_PROMPT, temperature=0.3):
        pieces.append(piece)
        on_token(piece)
    return "".join(pieces).strip()
