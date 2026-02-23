"""
detector.py – Hash a timetable and find what changed between two snapshots.
"""

import hashlib
import json


def hash_tt(tt: list[dict]) -> str:
    """
    Return an MD5 hex-digest of the serialised timetable.
    Used as a cheap equality check before doing deeper diff work.
    """
    # Sort keys for a deterministic serialisation
    serialised = json.dumps(tt, sort_keys=True, ensure_ascii=False)
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
    old_by_id = {l["id"]: l for l in old}
    new_by_id = {l["id"]: l for l in new}

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
        after  = new_by_id[lid]
        if before != after:
            changes.append({
                "type":   "changed",
                "lesson": after,
                "before": before,
                "after":  after,
            })
        elif after.get("change_type") == "exam" and before.get("change_type") != "exam":
            # Exam newly flagged on this lesson – always worth notifying about
            changes.append({"type": "exam", "lesson": after})

    return changes
