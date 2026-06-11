"""
ai.py – Generate a human-friendly summary of timetable changes.

Supports any OpenAI-compatible endpoint (OpenAI, LM Studio, Ollama,
Together AI, GitHub Models, etc.) via the AI_BASE_URL / AI_API_KEY
environment variables defined in config.py.
"""

import json
from datetime import datetime
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
    _AI_EXCEPTIONS = (Exception,)

_client_kwargs: dict = {"api_key": AI_API_KEY}
if AI_BASE_URL:
    _client_kwargs["base_url"] = AI_BASE_URL

_client = OpenAI(**_client_kwargs)


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


def _fallback_summary(changes: list[dict]) -> str:
    """Build a readable plain-text summary when the AI call fails or returns empty."""
    lines = [f"\u26a0\ufe0f Timetable changed ({len(changes)} change(s)):"]

    for change in changes:
        change_type = change.get("type", "changed")
        lesson = change.get("lesson") or change.get("after") or {}
        before = change.get("before") or {}

        subject = _get_subject(lesson)
        time = _fmt_time(lesson.get("start"))

        if change_type == "added":
            room = _get_room(lesson)
            lines.append(f"\u2795 ADDED: {subject} at {time} in {room}")

        elif change_type == "removed":
            lines.append(f"\ud83d\udd3a CANCELLED: {subject} at {time} — free period!")

        elif change_type == "exam":
            room = _get_room(lesson)
            lines.append(f"\ud83d\udfe1 EXAM: {subject} at {time} in {room}")

        elif change_type == "changed":
            # Show what actually changed between before and after
            details = []
            after = change.get("after") or lesson

            old_room = _get_room(before)
            new_room = _get_room(after)
            if old_room != new_room:
                details.append(f"room {old_room} \u2192 {new_room}")

            old_teacher = _get_teacher(before)
            new_teacher = _get_teacher(after)
            if old_teacher != new_teacher:
                details.append(f"teacher {old_teacher} \u2192 {new_teacher}")

            old_time = _fmt_time(before.get("start"))
            new_time = _fmt_time(after.get("start"))
            if old_time != new_time:
                details.append(f"time {old_time} \u2192 {new_time}")

            detail_str = ", ".join(details) if details else "details changed"
            lines.append(f"\ud83d� CHANGED: {subject} at {time} ({detail_str})")

        else:
            lines.append(f"\u2022 {change_type.upper()}: {subject} at {time}")

    return "\n".join(lines)


def explain(old_tt: list[dict], new_tt: list[dict], changes: list[dict]) -> str:
    """
    Ask the AI model to summarise the detected changes in plain language.
    Falls back to a structured plain-text summary if the model fails or
    returns an empty response.
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
        content = (response.choices[0].message.content or "").strip()
        if not content:
            print("[ai] Model returned empty response, using plain-text fallback.")
            return _fallback_summary(changes)
        return content
    except _AI_EXCEPTIONS as exc:
        print(f"[ai] Model request failed, using plain-text fallback: {exc}")
        return _fallback_summary(changes)
