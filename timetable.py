"""
timetable.py – Connect to WebUntis and fetch the upcoming timetable.
Uses the WebUntis JSON-RPC API directly via requests (no webuntis library).
"""

import requests
from datetime import date, timedelta
from config import (
    UNTIS_SERVER, UNTIS_SCHOOL,
    UNTIS_USER, UNTIS_PASSWORD,
    DAYS_AHEAD,
)

# Keywords in subject names that indicate an exam period
_EXAM_KEYWORDS = ("prüfung", "klausur", "test", "pruefung")


def get_session() -> requests.Session:
    """Open a requests.Session and log in to WebUntis. Returns the session with auth cookie set."""
    session = requests.Session()
    school_slug = UNTIS_SCHOOL.replace("/", "%2F").replace(" ", "+")
    url = f"https://{UNTIS_SERVER}/WebUntis/jsonrpc.do?school={school_slug}"

    payload = {
        "id": "1",
        "method": "authenticate",
        "params": {
            "user": UNTIS_USER,
            "password": UNTIS_PASSWORD,
            "client": "untis-watcher"
        },
        "jsonrpc": "2.0"
    }

    response = session.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise ConnectionError(f"WebUntis login failed: {data['error']}")

    session_id = data["result"]["sessionId"]
    session.cookies.set("JSESSIONID", session_id)
    session._untis_url = url  # store for later use in fetch()
    return session


def logout(session: requests.Session) -> None:
    """Log out of WebUntis."""
    try:
        session.post(session._untis_url, json={
            "id": "2",
            "method": "logout",
            "params": {},
            "jsonrpc": "2.0"
        })
    except Exception:
        pass  # best-effort logout


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


def fetch(session: requests.Session) -> list[dict]:
    """
    Return a sorted list of lesson dicts covering today + DAYS_AHEAD days.
    Each dict contains: id, start, end, subjects, teachers, rooms, code, change_type.
    """
    today = date.today()
    end   = today + timedelta(days=DAYS_AHEAD)

    # WebUntis expects dates as integers in YYYYMMDD format
    start_int = int(today.strftime("%Y%m%d"))
    end_int   = int(end.strftime("%Y%m%d"))

    payload = {
        "id": "3",
        "method": "getTimetable",
        "params": {
            "id": 0,
            "type": 5,  # type 5 = student timetable
            "startDate": start_int,
            "endDate": end_int,
        },
        "jsonrpc": "2.0"
    }

    response = session.post(session._untis_url, json=payload)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise ConnectionError(f"WebUntis timetable fetch failed: {data['error']}")

    raw_lessons = data.get("result", [])
    lessons = []

    for lesson in raw_lessons:
        # Extract names from subject/teacher/room lists
        subjects = [s.get("name", s.get("longName", "")) for s in lesson.get("su", [])]
        teachers = [t.get("name", t.get("longName", "")) for t in lesson.get("te", [])]
        rooms    = [r.get("name", r.get("longName", "")) for r in lesson.get("ro", [])]

        # code field: "cancelled", "irregular", or absent (normal)
        code = lesson.get("code", None)

        # Convert date/time integers to ISO strings
        # date: YYYYMMDD, startTime/endTime: HHMM
        raw_date  = str(lesson.get("date", ""))
        raw_start = str(lesson.get("startTime", "")).zfill(4)
        raw_end   = str(lesson.get("endTime", "")).zfill(4)

        start_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}T{raw_start[:2]}:{raw_start[2:]}"
        end_iso   = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}T{raw_end[:2]}:{raw_end[2:]}"

        lessons.append({
            "id":          lesson.get("id"),
            "start":       start_iso,
            "end":         end_iso,
            "subjects":    subjects,
            "teachers":    teachers,
            "rooms":       rooms,
            "code":        code,
            "change_type": _resolve_change_type(code, subjects),
        })

    # Stable ordering by start time, then by id for ties
    lessons.sort(key=lambda l: (l["start"], l["id"]))
    return lessons
