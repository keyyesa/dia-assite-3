"""Router Agent: decides which downstream path a request needs."""
from src import llm_client

SYSTEM_PROMPT = """You are the Router Agent in a diabetes clinical decision support system.
Decide which processing path the request needs, given the query and whether a lab report was uploaded.
Respond with exactly one label and nothing else:
KNOWLEDGE_ONLY  -> the question is general medical/guideline knowledge and does not depend on the uploaded report
REPORT_ONLY     -> the question is purely about interpreting the uploaded lab report values
BOTH            -> the question needs both guideline knowledge AND the uploaded report"""


def route(query: str, has_report: bool) -> str:
    # No report uploaded -> nothing to route, no LLM call needed.
    if not has_report:
        return "KNOWLEDGE_ONLY"

    prompt = f"Lab report uploaded: YES\nQuery: {query}\n\nLabel:"
    try:
        result = llm_client.generate(prompt, system_instruction=SYSTEM_PROMPT, temperature=0.0)
    except Exception:  # noqa: BLE001
        return "BOTH"
    result = (result or "").strip().upper()
    if "REPORT_ONLY" in result:
        return "REPORT_ONLY"
    if "KNOWLEDGE_ONLY" in result:
        return "KNOWLEDGE_ONLY"
    # Unclear/garbled output: safest default when a report exists is to use everything,
    # so the uploaded report is never silently ignored.
    return "BOTH"
