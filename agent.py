"""Sales Agent — Claude first, Groq fallback if credits run out."""

from config import CLAUDE_MODEL, ANTHROPIC_API_KEY, COMPANY_NAME, GROQ_API_KEY
from skills.prompts import SKILL_MAP
from database import log_interaction

_memory: dict[str, list[dict]] = {}
_GROQ_MODEL = "llama-3.3-70b-versatile"

SALES_SYSTEM = f"""You are an elite AI Sales Agent for {COMPANY_NAME} with 20+ years of B2B SaaS sales expertise.
You help with lead qualification, outreach, objection handling, deal coaching, competitor positioning, and pipeline management.
You are direct, specific, and action-oriented. You give concrete next steps, not vague advice.
You remember the context of this conversation."""


def _call(system: str, messages: list, max_tokens: int = 4096, model: str = None) -> str:
    """Try Claude first. If credits exhausted, fall back to Groq (free)."""
    # --- Try Anthropic ---
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            r = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
                model=model or CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return r.content[0].text
        except Exception as e:
            err = str(e).lower()
            if "credit" in err or "balance" in err or "billing" in err:
                pass  # fall through to Groq
            else:
                raise

    # --- Fall back to Groq ---
    if GROQ_API_KEY:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)
        msgs = [{"role": "system", "content": system}] + messages
        r = client.chat.completions.create(
            model=_GROQ_MODEL, messages=msgs, max_tokens=min(max_tokens, 2048), temperature=0.7
        )
        return r.choices[0].message.content

    raise RuntimeError("No working API. Add Anthropic credits or set GROQ_API_KEY.")


def run_skill(skill_id: str, user_input: str, context: str = "", session_id: str = "default", model: str = None, max_tokens: int = 4096) -> str:
    skill = SKILL_MAP.get(skill_id)
    if not skill:
        raise ValueError(f"Unknown skill '{skill_id}'. Available: {', '.join(SKILL_MAP.keys())}")

    full_input = f"Context:\n{context}\n\n---\n\n{user_input}" if context else user_input
    reply = _call(skill["prompt"], [{"role": "user", "content": full_input}], max_tokens, model)
    log_interaction(session_id, skill_id, user_input, reply)
    return reply


def chat(user_input: str, session_id: str = "default") -> str:
    history = _memory.get(session_id, [])
    messages = history + [{"role": "user", "content": user_input}]
    reply = _call(SALES_SYSTEM, messages, max_tokens=4096)
    _memory[session_id] = (messages + [{"role": "assistant", "content": reply}])[-20:]
    log_interaction(session_id, "chat", user_input, reply)
    return reply


def clear_memory(session_id: str = "default"):
    _memory.pop(session_id, None)
