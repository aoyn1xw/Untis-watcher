"""
ai.py – Generate a human-friendly summary of timetable changes.

When AI_ENABLED=false (or no API key is configured), explain() skips the
model call entirely and returns a structured plain-text summary built
directly from the raw Untis change data.

When AI is enabled, supports any OpenAI-compatible endpoint (OpenAI,
LM Studio, Ollama, Together AI, GitHub Models, etc.) via the
AI_BASE_URL / AI_API_KEY environment variables defined in config.py.
"""

import json
import logging
from datetime import datetime
from openai import OpenAI
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_ENABLED

logger = logging.getLogger("untis-watcher")

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
    _AI_EXCEPTIONS = (Exception,)

_client_kwargs: dict = {"api_key": AI_API_KEY}
if AI_BASE_URL:
    _client_kwargs["base_url"] = AI_BASE_URL

_client = OpenAI(**_client_kwargs)

# Emoji constants (proper Unicode codepoints, not surrogate pairs)
_EMOJI_WARNING   = "\u26a0\ufe0f"   # ⚠️
_EMOJI_ADDED     = "\u2795"         # ➕
_EMOJI_CANCELLED = "\U0001f53a"     # 🔺
_EMOJI_EXAM      = "\U0001f7e1"     # 🟡
_EMOJI_CHANGED   = "\U0001f7e2"     # 🟢
_EMOJI_BULLET    = "\u2022"         # •
_ARROW           = "\u2192"         # →


def _fmt_time(iso: str | None) -> str:
    """Convert ISO timestamp to HH:MM, e.g. '2026-06-08T08:20' -> '08:20'."""
    if not iso:
        return "?"
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except ValueError:
        return str(iso)


def _get_subject(lesson: dict) -> str:
    subjects = lesson.get("subjects") or []
    if subjects and isinstance(subjects[0], dict):
        return subjects[0].get("name") or subjects[0].get("longname") or "Unknown"
    if subjects and isinstance(subjects[0], str):
        return subjects[0]
    return "Unknown subject"


def _get_room(lesson: dict) -> str:
    rooms = lesson.get("rooms") or []
    if rooms and isinstance(rooms[0], dict):
        return rooms[0].get("name") or rooms[0].get("longname") or "?"
    if rooms and isinstance(rooms[0], str):
        return rooms[0]
    return "?"


def _get_teacher(lesson: dict) -> str:
    teachers = lesson.get("teachers") or []
    if teachers and isinstance(teachers[0], dict):
        return teachers[0].get("name") or teachers[0].get("longname") or "?"
    if teachers and isinstance(teachers[0], str):
        return teachers[0]
    return "?"


def _structured_summary(changes: list[dict]) -> str:
    """
    Build a readable plain-text summary directly from raw Untis change data.
    Used when AI is disabled or when the model call fails / returns empty.
    """
    lines = [f"{_EMOJI_WARNING} Timetable changed ({len(changes)} change(s)):"]

    for change in changes:
        change_type = change.get("type", "changed")
        lesson = change.get("lesson") or change.get("after") or {}
        before = change.get("before") or {}

        subject = _get_subject(lesson)
        time = _fmt_time(lesson.get("start"))

        if change_type == "added":
            room = _get_room(lesson)
            teacher = _get_teacher(lesson)
            lines.append(f"{_EMOJI_ADDED} ADDED: {subject} at {time} — {teacher}, room {room}")

        elif change_type == "removed":
            lines.append(f"{_EMOJI_CANCELLED} CANCELLED: {subject} at {time} — free period!")

        elif change_type == "exam":
            room = _get_room(lesson)
            teacher = _get_teacher(lesson)
            lines.append(f"{_EMOJI_EXAM} EXAM: {subject} at {time} — {teacher}, room {room}")

        elif change_type == "changed":
            after = change.get("after") or lesson
            details = []

            old_room = _get_room(before)
            new_room = _get_room(after)
            if old_room != new_room:
                details.append(f"room {old_room} {_ARROW} {new_room}")

            old_teacher = _get_teacher(before)
            new_teacher = _get_teacher(after)
            if old_teacher != new_teacher:
                details.append(f"teacher {old_teacher} {_ARROW} {new_teacher}")

            old_time = _fmt_time(before.get("start"))
            new_time = _fmt_time(after.get("start"))
            if old_time != new_time:
                details.append(f"time {old_time} {_ARROW} {new_time}")

            detail_str = ", ".join(details) if details else "details updated"
            lines.append(f"{_EMOJI_CHANGED} CHANGED: {subject} at {time} ({detail_str})")

        else:
            lines.append(f"{_EMOJI_BULLET} {change_type.upper()}: {subject} at {time}")

    return "\n".join(lines)


def explain(old_tt: list[dict], new_tt: list[dict], changes: list[dict]) -> str:
    """
    Return a human-friendly summary of the detected timetable changes.

    If AI_ENABLED is False, returns the structured plain-text summary
    immediately without making any network call.

    If AI_ENABLED is True, calls the configured model and falls back to
    the structured summary on error or empty response.
    """
    if not AI_ENABLED:
        logger.info("[ai] AI disabled — using structured plain-text summary.")
        return _structured_summary(changes)

    changes_json = json.dumps(changes, ensure_ascii=False, indent=2)

    prompt = f"""You are a helpful school assistant for a student named Erdi at \
Gesamtschule Uellendahl/Katernberg in Germany.

Explain the timetable changes in friendly, clear English.
Follow these rules:
- \"cancelled\" (Entfall {_EMOJI_CANCELLED}): tell Erdi he has a free period
- \"irregular\" (\u00c4nderung {_EMOJI_CHANGED}): explain exactly what changed (room, teacher, or time)
- Exams (Pr\u00fcfung {_EMOJI_EXAM}): always mention these FIRST, they are important
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
        content = (response.choices[0].message.content or "").strip()
        if not content:
            logger.warning("[ai] Model returned empty response — falling back to structured summary.")
            return _structured_summary(changes)
        return content
    except _AI_EXCEPTIONS as exc:
        logger.warning("[ai] Model request failed (%s) — falling back to structured summary.", exc)
        return _structured_summary(changes)
