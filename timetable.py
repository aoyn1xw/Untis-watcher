"""
timetable.py – Connect to WebUntis and fetch the upcoming timetable.
"""

from datetime import date, timedelta
from config import (
    UNTIS_SERVER, UNTIS_SCHOOL,
    UNTIS_USER, UNTIS_PASSWORD,
    DAYS_AHEAD,
)


def get_session() -> requests.Session:
    """Open and log in to a WebUntis session."""
    s = webuntis.session.Session(
        server=UNTIS_SERVER,
        school=UNTIS_SCHOOL,
        username=UNTIS_USER,
        password=UNTIS_PASSWORD,
        useragent="untis-watcher/1.0",
    )
    s.login()
    return s


def _names(obj_list) -> list[str]:
    """Extract .name from a list of WebUntis objects, gracefully."""
    return [o.name for o in obj_list if hasattr(o, "name")]


# Keywords in subject names that indicate an exam period
_EXAM_KEYWORDS = ("prüfung", "klausur", "test", "pruefung")


def _resolve_change_type(code: str | None, subjects: list[str]) -> str:
    """
    Map the raw WebUntis code + subject name to a human-readable change type.

    Codes used by WebUntis:
      None / "regular" → normal lesson
      "irregular"      → Änderung 🟢 (room, teacher, or time changed)
      "cancelled"      → Entfall 🔺 (lesson dropped)

    If the subject name contains a known exam keyword the lesson is
    classified as "exam" regardless of its code.
    """
    subject_lower = " ".join(subjects).lower()
    if any(kw in subject_lower for kw in _EXAM_KEYWORDS):
        return "exam"
    if code == "cancelled":
        return "cancelled"
    if code == "irregular":
        return "changed"
    return "normal"


def fetch(session: webuntis.session.Session) -> list[dict]:
    """
    Return a sorted list of lesson dicts covering today + DAYS_AHEAD days.
    Each dict contains: id, start, end, subjects, teachers, rooms, code, change_type.
    """
    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)

    raw_lessons = session.timetable(start=today, end=end)

    lessons = []
    for lesson in raw_lessons:
        # lesson.code is an enum-like value: None / "cancelled" / "irregular"
        code = (
            lesson.code.name
            if hasattr(lesson.code, "name")
            else (str(lesson.code) if lesson.code else None)
        )
        subjects = _names(lesson.subjects)

        lessons.append({
            "id":          lesson.id,
            "start":       lesson.start.isoformat(),
            "end":         lesson.end.isoformat(),
            "subjects":    subjects,
            "teachers":    _names(lesson.teachers),
            "rooms":       _names(lesson.rooms),
            "code":        code,
            "change_type": _resolve_change_type(code, subjects),
        })

    # Stable ordering by start time, then by id for ties
    lessons.sort(key=lambda l: (l["start"], l["id"]))
    return lessons
