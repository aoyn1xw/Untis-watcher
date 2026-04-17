"""
detector.py – Hash a timetable and find what changed between two snapshots.
"""

import hashlib
import json

# Only compare fields that represent meaningful timetable changes:
# start/end time, subject list, raw code, and resolved change type.
# This intentionally ignores incidental metadata noise from WebUntis
# (for example teacher/room metadata reshuffling that doesn't affect
# the core lesson change semantics).
COMPARE_KEYS = {"start", "end", "subjects", "code", "change_type"}
_MISSING_ID_SORT_KEY = "\uffff__missing_lesson_id__"


def _lesson_sig(lesson: dict) -> dict:
    """Return only the lesson fields relevant for change detection."""
    return {key: lesson.get(key) for key in COMPARE_KEYS}


def _normalise_lesson_id(lesson_id) -> str | None:
    """Normalise lesson IDs so mixed int/str IDs map to the same key."""
    if lesson_id is None:
        return None
    return str(lesson_id)


def _missing_id_base_key(lesson: dict) -> str:
    """Build a stable fallback key base for lessons that have no ID."""
    sig = _lesson_sig(lesson)
    return f"missing:{json.dumps(sig, sort_keys=True, ensure_ascii=False)}"


def _index_lessons_by_id(tt: list[dict]) -> dict[str, dict]:
    """
    Index lessons by normalised ID.
    For missing IDs, use a deterministic fallback key plus an occurrence suffix
    to avoid overwriting duplicate lessons with equivalent signatures.
    """
    indexed: dict[str, dict] = {}
    missing_counts: dict[str, int] = {}

    for lesson in tt:
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


def _normalise_tt(tt: list[dict]) -> list[dict]:
    """Return a deterministic, comparison-aligned timetable representation."""
    return sorted(
        [{"id": _normalise_lesson_id(lesson.get("id")), **_lesson_sig(lesson)} for lesson in tt],
        key=lambda lesson: lesson["id"] if lesson["id"] is not None else _MISSING_ID_SORT_KEY,
    )


def hash_tt(tt: list[dict]) -> str:
    """
    Return an MD5 hex-digest of the serialised timetable.
    Used as a cheap equality check before doing deeper diff work.
    """
    # Hash the same meaningful lesson representation used for comparisons,
    # so incidental metadata changes do not trigger false positives.
    serialised = json.dumps(_normalise_tt(tt), sort_keys=True, ensure_ascii=False)
    return hashlib.md5(serialised.encode()).hexdigest()


def find_changes(old: list[dict], new: list[dict]) -> list[dict]:
    """
    Compare two timetable snapshots by lesson ID.

    Returns a list of change dicts, each with:
      - type:   "added" | "removed" | "changed"
      - lesson: the new lesson (added / changed) or the old lesson (removed)
      - before: previous lesson state  (only for "changed")
      - after:  new lesson state        (only for "changed")
    """
    old_by_id = _index_lessons_by_id(old)
    new_by_id = _index_lessons_by_id(new)

    changes = []

    # Lessons present in new but not in old → added
    for lid, lesson in new_by_id.items():
        if lid not in old_by_id:
            changes.append({"type": "added", "lesson": lesson})

    # Lessons present in old but not in new → removed
    for lid, lesson in old_by_id.items():
        if lid not in new_by_id:
            changes.append({"type": "removed", "lesson": lesson})

    # Lessons in both → check for modifications or newly-flagged exams
    for lid in old_by_id.keys() & new_by_id.keys():
        before = old_by_id[lid]
        after = new_by_id[lid]
        if _lesson_sig(before) != _lesson_sig(after):
            changes.append({
                "type": "changed",
                "lesson": after,
                "before": before,
                "after": after,
            })
        elif after.get("change_type") == "exam" and before.get("change_type") != "exam":
            # Exam newly flagged on this lesson – always worth notifying about
            changes.append({"type": "exam", "lesson": after})

    return changes
