"""Sales Agent — Claude API core with skill routing and memory."""

import anthropic
from config import CLAUDE_MODEL
from skills.prompts import SKILL_MAP
from database import log_interaction

_memory: dict[str, list[dict]] = {}


def run_skill(skill_id: str, user_input: str, context: str = "", session_id: str = "default", model: str = None, max_tokens: int = 4096) -> str:
    skill = SKILL_MAP.get(skill_id)
    if not skill:
        raise ValueError(f"Unknown skill '{skill_id}'. Available: {', '.join(SKILL_MAP.keys())}")

    client = anthropic.Anthropic()
    full_input = f"Context:\n{context}\n\n---\n\n{user_input}" if context else user_input

    response = client.messages.create(
        model=model or CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=skill["prompt"],
        messages=[{"role": "user", "content": full_input}],
    )

    reply = response.content[0].text
    log_interaction(session_id, skill_id, user_input, reply)
    return reply


def chat(user_input: str, session_id: str = "default") -> str:
    client = anthropic.Anthropic()

    system = f"""You are an elite AI Sales Agent for {__import__('config').COMPANY_NAME} with 20+ years of B2B SaaS sales expertise.
You help with lead qualification, outreach, objection handling, deal coaching, competitor positioning, and pipeline management.
You are direct, specific, and action-oriented. You give concrete next steps, not vague advice.
You remember the context of this conversation."""

    history = _memory.get(session_id, [])
    messages = history + [{"role": "user", "content": user_input}]
    response = client.messages.create(model=CLAUDE_MODEL, max_tokens=4096, system=system, messages=messages)
    reply = response.content[0].text
    _memory[session_id] = (messages + [{"role": "assistant", "content": reply}])[-20:]
    log_interaction(session_id, "chat", user_input, reply)
    return reply


def clear_memory(session_id: str = "default"):
    _memory.pop(session_id, None)
