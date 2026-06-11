"""
ai.py – Generate a human-friendly summary of timetable changes.

Supports any OpenAI-compatible endpoint (OpenAI, LM Studio, Ollama,
Together AI, GitHub Models, etc.) via the AI_BASE_URL / AI_API_KEY
environment variables defined in config.py.
"""

import json
from openai import OpenAI
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL

try:
    from openai import (
        APIConnectionError,
        APIError,
        APITimeoutError,
        AuthenticationError,
        RateLimitError,
    )
    _AI_EXCEPTIONS = (
        APIError,
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        RateLimitError,
    )
except ImportError:
    # Fallback when exception classes differ across SDK versions.
    _AI_EXCEPTIONS = (Exception,)

# Build client kwargs – only pass base_url when explicitly configured so the
# default SDK endpoint (api.openai.com) is used when AI_BASE_URL is unset.
_client_kwargs: dict = {"api_key": AI_API_KEY}
if AI_BASE_URL:
    _client_kwargs["base_url"] = AI_BASE_URL

_client = OpenAI(**_client_kwargs)


def _fallback_summary(changes: list[dict]) -> str:
    """Build a plain-text summary when the AI API call fails."""
    lines = [f"\u26a0\ufe0f Timetable changed ({len(changes)} change(s)):"]

    for change in changes:
        lesson = change.get("lesson", {})
        subjects = lesson.get("subjects") or []
        subject = subjects[0] if subjects else "Unknown subject"
        start = lesson.get("start", "unknown time")
        change_label = (
            "CANCELLED"
            if lesson.get("change_type") == "cancelled"
            else str(change.get("type", "changed")).upper()
        )
        lines.append(f"\u2022 {change_label}: {subject} at {start}")

    return "\n".join(lines)


def explain(old_tt: list[dict], new_tt: list[dict], changes: list[dict]) -> str:
    """
    Ask the AI model to summarise the detected changes in plain language.
    The full changes list is passed as JSON so the model can reason precisely.
    Returns the model's reply as a string.
    """
    changes_json = json.dumps(changes, ensure_ascii=False, indent=2)

    prompt = f"""You are a helpful school assistant for a student named Erdi at \
Gesamtschule Uellendahl/Katernberg in Germany.

Explain the timetable changes in friendly, clear English.
Follow these rules:
- \"cancelled\" (Entfall \U0001f53a): tell Erdi he has a free period
- \"irregular\" (\u00c4nderung \U0001f7e2): explain exactly what changed (room, teacher, or time)
- Exams (Pr\u00fcfung \U0001f7e1): always mention these FIRST, they are important
- Be specific: always include subject name, teacher code, time, and room
- Keep the summary to 3-5 sentences max
- If multiple things changed, use a short numbered list inside the message
- End with a reassuring line if nothing major changed

Changes detected:
{changes_json}
"""

    try:
        response = _client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except _AI_EXCEPTIONS as exc:
        print(f"[ai] Model request failed, using plain-text fallback: {exc}")
        return _fallback_summary(changes)
