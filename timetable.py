"""
timetable.py – Connect to WebUntis and fetch the upcoming timetable.
Uses the WebUntis mobile app API via requests.
"""

import requests
from datetime import date, timedelta
from config import (
    UNTIS_SERVER, UNTIS_SCHOOL,
    UNTIS_USER, UNTIS_PASSWORD,
    UNTIS_ELEMENT_TYPE, UNTIS_ELEMENT_ID,
)

# Keywords in subject names that indicate an exam period
_EXAM_KEYWORDS = ("prüfung", "klausur", "test", "pruefung")

# Element type constants for the mobile API
_TYPE_TEACHER = 2
_TYPE_SUBJECT = 3
_TYPE_ROOM    = 4


def get_session() -> requests.Session:
    """Open a requests.Session and log in to WebUntis via JSON-RPC API. Returns the session with auth cookie set."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })

    # Use JSON-RPC API for login
    api_url = f"https://{UNTIS_SERVER}/WebUntis/jsonrpc.do?school={UNTIS_SCHOOL}"
    session._untis_url = api_url  # Store for logout
    
    response = session.post(api_url, json={
        "id": "1",
        "method": "authenticate",
        "params": {
            "user": UNTIS_USER,
            "password": UNTIS_PASSWORD,
            "client": "untis-watcher"
        },
        "jsonrpc": "2.0"
    })
    response.raise_for_status()
    
    data = response.json()
    if "error" in data:
        raise ConnectionError(f"WebUntis login failed: {data['error']}")
    
    if "result" not in data or "sessionId" not in data["result"]:
        raise ConnectionError(f"WebUntis login failed: No session ID returned")
    
    session._session_id = data["result"]["sessionId"]
    session._person_id = data["result"].get("personId", UNTIS_ELEMENT_ID)

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
    subject_lower = " ".join(subjects).lower()
    if any(kw in subject_lower for kw in _EXAM_KEYWORDS):
        return "exam"
    if code == "cancelled":
        return "cancelled"
    if code == "irregular":
        return "changed"
    return "normal"


def fetch(session: requests.Session) -> list[dict]:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Use JSON-RPC API to get timetable
    response = session.post(session._untis_url, json={
        "id": "3",
        "method": "getTimetable",
        "params": {
            "options": {
                "element": {
                    "id": session._person_id,
                    "type": UNTIS_ELEMENT_TYPE
                },
                "startDate": week_start.strftime("%Y%m%d"),
                "endDate": week_end.strftime("%Y%m%d"),
                "showInfo": True,
                "showSubstText": True,
                "showLsText": True,
                "showLsNumber": True,
                "showStudentgroup": True,
                "klasseFields": ["id", "name", "longname"],
                "roomFields": ["id", "name", "longname"],
                "subjectFields": ["id", "name", "longname"],
                "teacherFields": ["id", "name", "longname"]
            }
        },
        "jsonrpc": "2.0"
    })
    response.raise_for_status()
    
    data = response.json()
    if "error" in data:
        raise ConnectionError(f"Failed to fetch timetable: {data['error']}")
    
    result = data.get("result", [])
    
    # The result is directly the list of periods
    if isinstance(result, list):
        periods = result
        # Build empty lookup maps since JSON-RPC doesn't return them separately
        klassen = {}
        teachers = {}
        subjects = {}
        rooms = {}
    else:
        # Fallback if it's a dict structure
        periods = result.get("result", [])
        klassen = {k["id"]: k.get("name", k.get("longname", "")) for k in result.get("klassen", [])}
        teachers = {t["id"]: t.get("name", t.get("longname", "")) for t in result.get("teachers", [])}
        subjects = {s["id"]: s.get("name", s.get("longname", "")) for s in result.get("subjects", [])}
        rooms = {r["id"]: r.get("name", r.get("longname", "")) for r in result.get("rooms", [])}

    lessons = []
    for period in periods:
        raw_date = str(period.get("date", ""))
        raw_start = str(period.get("startTime", "")).zfill(4)
        raw_end = str(period.get("endTime", "")).zfill(4)

        start_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}T{raw_start[:2]}:{raw_start[2:]}"
        end_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}T{raw_end[:2]}:{raw_end[2:]}"

        # Get subjects, teachers, rooms from period - they may have IDs or be embedded
        period_subjects = []
        period_teachers = []
        period_rooms = []
        
        # Try to get from embedded data (su, te, ro arrays)
        for s in period.get("su", []):
            if isinstance(s, dict):
                name = subjects.get(s.get("id"), s.get("name", s.get("longname", "")))
                if name:
                    period_subjects.append(name)
        
        for t in period.get("te", []):
            if isinstance(t, dict):
                name = teachers.get(t.get("id"), t.get("name", t.get("longname", "")))
                if name:
                    period_teachers.append(name)
        
        for r in period.get("ro", []):
            if isinstance(r, dict):
                name = rooms.get(r.get("id"), r.get("name", r.get("longname", "")))
                if name:
                    period_rooms.append(name)

        # Determine code and change type
        code_val = period.get("code")
        is_cancelled = code_val == "cancelled" or period.get("cellState") == "CANCEL"
        
        if is_cancelled:
            code = "cancelled"
        elif code_val == "irregular" or period.get("cellState") in ["SUBST", "SHIFT"]:
            code = "irregular"
        else:
            code = None

        lessons.append({
            "id": period.get("id"),
            "start": start_iso,
            "end": end_iso,
            "subjects": period_subjects,
            "teachers": period_teachers,
            "rooms": period_rooms,
            "code": code,
            "change_type": _resolve_change_type(code, period_subjects),
        })

    lessons.sort(key=lambda l: (l["start"], l["id"]))
    return lessons
