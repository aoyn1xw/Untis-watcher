"""
detector.py – Deterministically normalise, compare, and diff timetable snapshots.
"""

import hashlib
import json
from typing import Any

_MISSING_ID_SORT_KEY = "\uffff__missing_lesson_id__"
_MISSING_ID_MATCH_KEYS = {"start", "end", "subjects"}
_ORDER_INSENSITIVE_LIST_FIELDS = {"subjects", "teachers", "rooms"}


def _normalise_lesson_id(lesson_id: Any) -> str | None:
    """Normalise lesson IDs so mixed int/str IDs map to the same key."""
    if lesson_id is None:
        return None
    return str(lesson_id)


def _normalise_value(value: Any, *, field_name: str | None = None) -> Any:
    """Return a JSON-stable representation for deep comparison."""
    if isinstance(value, dict):
        return {str(key): _normalise_value(value[key], field_name=str(key)) for key in sorted(value)}

    if isinstance(value, list):
        items = [_normalise_value(item) for item in value]
        if field_name in _ORDER_INSENSITIVE_LIST_FIELDS:
            return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
        return items

    if isinstance(value, tuple):
        return [_normalise_value(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def _lesson_sort_key(lesson: dict) -> tuple[str, str, str, str]:
    normalised_id = _normalise_lesson_id(lesson.get("id")) or _MISSING_ID_SORT_KEY
    serialised = json.dumps(lesson, sort_keys=True, ensure_ascii=False)
    return (str(lesson.get("start") or ""), str(lesson.get("end") or ""), normalised_id, serialised)


def normalise_timetable(tt: list[dict] | None) -> list[dict]:
    """Return a deterministic, deep-comparable timetable representation."""
    if not tt:
        return []

    normalised = []
    for lesson in tt:
        if not isinstance(lesson, dict):
            continue

        normalised_lesson = _normalise_value(lesson)
        normalised_lesson["id"] = _normalise_lesson_id(lesson.get("id"))
        normalised.append(normalised_lesson)

    return sorted(normalised, key=_lesson_sort_key)


def timetables_equal(old: list[dict] | None, new: list[dict] | None) -> bool:
    """Deep-compare two timetable snapshots after deterministic normalisation."""
    return normalise_timetable(old) == normalise_timetable(new)


def _serialise_normalised(tt: list[dict] | None) -> str:
    return json.dumps(normalise_timetable(tt), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def hash_tt(tt: list[dict] | None) -> str:
    """Return an MD5 hex-digest of the deep-normalised timetable."""
    return hashlib.md5(_serialise_normalised(tt).encode()).hexdigest()


def _missing_id_base_key(lesson: dict) -> str:
    """
    Build a fallback key base for lessons that have no ID.
    Uses a stable subset so state-like fields can change without turning one
    lesson update into remove+add.
    """
    sig = {key: lesson.get(key) for key in _MISSING_ID_MATCH_KEYS}
    return f"missing:{json.dumps(_normalise_value(sig), sort_keys=True, ensure_ascii=False)}"


def _index_lessons_by_id(tt: list[dict] | None) -> dict[str, dict]:
    """
    Index lessons by normalised ID.
    For missing IDs, use a deterministic fallback key plus an occurrence suffix.
    """
    indexed: dict[str, dict] = {}
    missing_counts: dict[str, int] = {}

    for lesson in normalise_timetable(tt):
        lesson_id = _normalise_lesson_id(lesson.get("id"))
        if lesson_id is None:
            base_key = _missing_id_base_key(lesson)
            occurrence = missing_counts.get(base_key, 0)
            missing_counts[base_key] = occurrence + 1
            key = f"{base_key}#{occurrence}"
        else:
            key = f"id:{lesson_id}"
        indexed[key] = lesson

    return indexed


def find_changes(old: list[dict] | None, new: list[dict] | None) -> list[dict]:
    """
    Deep-compare two normalised timetable snapshots by lesson ID.

    Returns a list of change dicts, each with:
      - type:   "added" | "removed" | "changed" | "exam"
      - lesson: the new lesson (added / changed) or the old lesson (removed)
      - before: previous lesson state  (only for "changed")
      - after:  new lesson state        (only for "changed")
    """
    old_by_id = _index_lessons_by_id(old)
    new_by_id = _index_lessons_by_id(new)

    changes = []

    for lid, lesson in new_by_id.items():
        if lid not in old_by_id:
            changes.append({"type": "added", "lesson": lesson})

    for lid, lesson in old_by_id.items():
        if lid not in new_by_id:
            changes.append({"type": "removed", "lesson": lesson})

    for lid in sorted(old_by_id.keys() & new_by_id.keys()):
        before = old_by_id[lid]
        after = new_by_id[lid]
        if before != after:
            change_type = "exam" if after.get("change_type") == "exam" and before.get("change_type") != "exam" else "changed"
            changes.append({
                "type": change_type,
                "lesson": after,
                "before": before,
                "after": after,
            })

    return changes
