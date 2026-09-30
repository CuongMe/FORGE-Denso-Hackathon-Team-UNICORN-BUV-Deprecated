from __future__ import annotations


GROUNDED_PROMPT_VERSION = "grounded-answer-v2"
GROUNDED_SYSTEM_PROMPT = (
    "You are FORGE, a factory operations assistant. "
    "Answer only from the supplied evidence. "
    "If the evidence is weak or incomplete, clearly state that uncertainty. "
    "If the evidence cannot answer the question, reply exactly: ABSTAIN. "
    "Never invent procedures, values, units, dates, or citations."
)

PROMPT_REGISTRY = {
    "grounded_answer": {
        "version": GROUNDED_PROMPT_VERSION,
        "text": GROUNDED_SYSTEM_PROMPT,
    },
}


def grounded_system_prompt() -> str:
    return PROMPT_REGISTRY["grounded_answer"]["text"]
