"""
ai.py – Generate a human-friendly summary of timetable changes via GitHub Models.
The OpenAI SDK is used with a custom base_url pointing at the Azure-hosted endpoint.
"""

import json
from openai import OpenAI
from config import GITHUB_TOKEN, AI_MODEL

# GitHub Models exposes an OpenAI-compatible REST API
_client = OpenAI(
        base_url="https://models.github.ai/inference",
    api_key=GITHUB_TOKEN,
)


def _fallback_summary(changes: list[dict]) -> str:
    """Build a plain-text summary when the AI API call fails."""
    lines = [f"⚠️ Timetable changed ({len(changes)} change(s)):"]

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
        lines.append(f"• {change_label}: {subject} at {start}")

    return "\n".join(lines)


def explain(old_tt: list[dict], new_tt: list[dict], changes: list[dict]) -> str:
    """
    Ask the AI model to summarise the detected changes in plain language.
    The full changes list is passed as JSON so the model can reason precisely.
    Returns the model's reply as a string.
    """
    # Serialise changes to JSON for the prompt – the model receives full detail
    changes_json = json.dumps(changes, ensure_ascii=False, indent=2)

    prompt = f"""You are a helpful school assistant for a student named Erdi at \
Gesamtschule Uellendahl/Katernberg in Germany.

Explain the timetable changes in friendly, clear English.
Follow these rules:
- "cancelled" (Entfall 🔺): tell Erdi he has a free period
- "irregular" (Änderung 🟢): explain exactly what changed (room, teacher, or time)
- Exams (Prüfung 🟡): always mention these FIRST, they are important
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
            temperature=0.5,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return _fallback_summary(changes)
