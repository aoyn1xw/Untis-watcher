"""
timetable.py – Connect to WebUntis and fetch the upcoming timetable.
Uses the WebUntis mobile app API via requests.
"""

import requests
from datetime import date, timedelta
from config import (
    UNTIS_SERVER, UNTIS_SCHOOL,
    UNTIS_USER, UNTIS_PASSWORD,
)

# Keywords in subject names that indicate an exam period
_EXAM_KEYWORDS = ("prüfung", "klausur", "test", "pruefung")

# Element type constants for the mobile API
_TYPE_TEACHER = 2
_TYPE_SUBJECT = 3
_TYPE_ROOM    = 4


def get_session() -> requests.Session:
    """Open a requests.Session and log in to WebUntis via the mobile app API. Returns the session with auth cookie set."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "de-DE,de;q=0.9",
        "Origin": f"https://{UNTIS_SERVER}",
        "Referer": f"https://{UNTIS_SERVER}/WebUntis/",
    })

    login_url = f"https://{UNTIS_SERVER}/WebUntis/j_spring_security_check"

    response = session.post(login_url, data={
        "j_username": UNTIS_USER,
        "j_password": UNTIS_PASSWORD,
        "school": UNTIS_SCHOOL,
        "token": "",
    })
    response.raise_for_status()

    if "failed" in response.url or "error" in response.url:
        raise ConnectionError(f"WebUntis login failed: {response.url}")

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

    url = f"https://{UNTIS_SERVER}/WebUntis/api/public/timetable/weekly/data"
    params = {
        "elementType": 5,
        "elementId": 0,
        "date": week_start.strftime("%Y-%m-%d"),
        "formatId": 1,
    }

    response = session.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    result_data = data.get("data", {}).get("result", {}).get("data", {})
    element_periods = result_data.get("elementPeriods", {})
    elements = result_data.get("elements", [])

    # Build lookup: (type, id) -> name
    element_map: dict[tuple[int, int], str] = {}
    for el in elements:
        element_map[(el.get("type"), el.get("id"))] = el.get("name", el.get("longName", ""))

    lessons = []
    for periods in element_periods.values():
        for period in periods:
            raw_date  = str(period.get("date", ""))
            raw_start = str(period.get("startTime", "")).zfill(4)
            raw_end   = str(period.get("endTime", "")).zfill(4)

            start_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}T{raw_start[:2]}:{raw_start[2:]}"
            end_iso   = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}T{raw_end[:2]}:{raw_end[2:]}"

            period_elements = period.get("elements", [])
            subjects = [element_map[(t, e["id"])] for e in period_elements if (t := e.get("type")) == _TYPE_SUBJECT and (t, e["id"]) in element_map]
            teachers = [element_map[(t, e["id"])] for e in period_elements if (t := e.get("type")) == _TYPE_TEACHER and (t, e["id"]) in element_map]
            rooms    = [element_map[(t, e["id"])] for e in period_elements if (t := e.get("type")) == _TYPE_ROOM    and (t, e["id"]) in element_map]

            cell_state = period.get("cellState", "")
            is_cancelled = period.get("is", {}).get("cancelled", False)

            if cell_state == "CANCELLED" or is_cancelled:
                code = "cancelled"
            elif cell_state == "IRREGULAR":
                code = "irregular"
            else:
                code = None

            lessons.append({
                "id":          period.get("id"),
                "start":       start_iso,
                "end":         end_iso,
                "subjects":    subjects,
                "teachers":    teachers,
                "rooms":       rooms,
                "code":        code,
                "change_type": _resolve_change_type(code, subjects),
            })

    lessons.sort(key=lambda l: (l["start"], l["id"]))
    return lessons
