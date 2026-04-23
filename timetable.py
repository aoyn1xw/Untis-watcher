"""
timetable.py – Connect to WebUntis and fetch the upcoming timetable.
Uses the WebUntis mobile app API via requests.
"""

import base64
import time
import requests
from datetime import date, timedelta
from config import (
    UNTIS_SERVER, UNTIS_SCHOOL,
    UNTIS_USER, UNTIS_PASSWORD,
    UNTIS_ELEMENT_TYPE, UNTIS_ELEMENT_ID, DAYS_AHEAD,
    UNTIS_TENANT_ID, UNTIS_CLIENT_ID, UNTIS_API_PASSWORD,
)

# Keywords in subject names that indicate an exam period
_EXAM_KEYWORDS = ("prüfung", "klausur", "test", "pruefung")

# Element type constants for the mobile API
_TYPE_TEACHER = 2
_TYPE_SUBJECT = 3
_TYPE_ROOM    = 4
# requests timeout: (connect_timeout_seconds, read_timeout_seconds)
_REQUEST_TIMEOUT = (10, 30)
_REST_TOKEN_URL = "https://api.webuntis.com/WebUntis/api/sso/v3/{tenant_id}/token?grant_type=client_credentials"
_REST_TIMETABLE_URL = "https://api.webuntis.com/WebUntis/api/rest/extern/v3/timetable"
_TOKEN_EXPIRY_SAFETY_SECONDS = 15

_token_cache: dict[str, float | str | None] = {
    "access_token": None,
    "expires_at": 0.0,
}


def _rest_creds_status() -> tuple[bool, list[str]]:
    provided = {
        "UNTIS_TENANT_ID": bool(UNTIS_TENANT_ID),
        "UNTIS_CLIENT_ID": bool(UNTIS_CLIENT_ID),
        "UNTIS_API_PASSWORD": bool(UNTIS_API_PASSWORD),
    }
    missing = [name for name, is_set in provided.items() if not is_set]
    all_set = all(provided.values())
    any_set = any(provided.values())
    if any_set and not all_set:
        return False, missing
    return all_set, missing


def _to_iso_minute(value: str | int | None) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)

    # yyyyMMddTHHmm
    if len(text) >= 13 and text[8] == "T" and text[:8].isdigit() and text[9:13].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}T{text[9:11]}:{text[11:13]}"

    # yyyy-MM-ddTHH:mm[:ss][...]
    if len(text) >= 16 and text[4] == "-" and text[7] == "-" and text[10] == "T":
        return text[:16]

    return ""


def _from_date_and_time(raw_date: str | int | None, raw_time: str | int | None) -> str:
    if raw_date is None or raw_time is None:
        return ""

    date_text = str(raw_date).strip()
    time_text = str(raw_time).strip().zfill(4)

    if len(date_text) != 8 or not date_text.isdigit() or len(time_text) < 4 or not time_text[:4].isdigit():
        return ""

    return f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]}T{time_text[:2]}:{time_text[2:4]}"


def _extract_names(value) -> list[str]:
    if value is None:
        return []

    entries = value if isinstance(value, list) else [value]
    names = []
    for entry in entries:
        if isinstance(entry, str):
            if entry:
                names.append(entry)
            continue

        if not isinstance(entry, dict):
            continue

        for key in ("name", "longname", "longName", "displayName", "fullName", "shortName", "code", "label"):
            candidate = entry.get(key)
            if isinstance(candidate, str) and candidate:
                names.append(candidate)
                break

    return names


def get_bearer_token() -> str:
    """Return a cached bearer token for WebUntis REST API or refresh when expired."""
    now = time.time()
    cached_token = _token_cache.get("access_token")
    cached_expiry = float(_token_cache.get("expires_at") or 0)
    if isinstance(cached_token, str) and cached_token and now < (cached_expiry - _TOKEN_EXPIRY_SAFETY_SECONDS):
        return cached_token

    if not (UNTIS_TENANT_ID and UNTIS_CLIENT_ID and UNTIS_API_PASSWORD):
        raise ConnectionError("REST token request requires UNTIS_TENANT_ID, UNTIS_CLIENT_ID, and UNTIS_API_PASSWORD.")

    basic = base64.b64encode(f"{UNTIS_CLIENT_ID}:{UNTIS_API_PASSWORD}".encode("utf-8")).decode("ascii")
    url = _REST_TOKEN_URL.format(tenant_id=UNTIS_TENANT_ID)

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data="",
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ConnectionError(f"Failed to get WebUntis REST bearer token: {exc}") from exc
    except ValueError as exc:
        raise ConnectionError("Failed to parse WebUntis REST token response as JSON.") from exc

    token = payload.get("access_token")
    expires_in = payload.get("expires_in", 0)
    if not isinstance(token, str) or not token:
        raise ConnectionError("WebUntis REST token response did not contain a valid access_token.")

    try:
        expires_in_seconds = int(expires_in)
    except (TypeError, ValueError):
        expires_in_seconds = 0

    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + max(expires_in_seconds, 0)
    return token


def get_session() -> requests.Session | dict:
    """Open a requests.Session and log in to WebUntis via JSON-RPC API. Returns the session with auth cookie set."""
    use_rest, missing_rest = _rest_creds_status()
    if not use_rest and missing_rest and any([UNTIS_TENANT_ID, UNTIS_CLIENT_ID, UNTIS_API_PASSWORD]):
        raise ConnectionError(
            "Incomplete REST credentials. Set all of UNTIS_TENANT_ID, UNTIS_CLIENT_ID, UNTIS_API_PASSWORD. "
            f"Missing: {', '.join(missing_rest)}"
        )

    if use_rest:
        return {
            "mode": "rest",
            "token": get_bearer_token(),
        }

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
    }, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    
    data = response.json()
    if "error" in data:
        raise ConnectionError(f"WebUntis login failed: {data['error']}")
    
    if "result" not in data or "sessionId" not in data["result"]:
        raise ConnectionError(f"WebUntis login failed: No session ID returned")
    
    session._session_id = data["result"]["sessionId"]
    session._person_id = data["result"].get("personId", UNTIS_ELEMENT_ID)

    return session


def logout(session: requests.Session | dict) -> None:
    """Log out of WebUntis."""
    if isinstance(session, dict) and session.get("mode") == "rest":
        return

    try:
        session.post(session._untis_url, json={
            "id": "2",
            "method": "logout",
            "params": {},
            "jsonrpc": "2.0"
        }, timeout=_REQUEST_TIMEOUT)
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


def fetch_rest(token: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    raw_periods = []
    page = 1
    while True:
        try:
            response = requests.get(
                _REST_TIMETABLE_URL,
                headers=headers,
                params={"page": page},
                timeout=_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ConnectionError(f"Failed to fetch timetable from WebUntis REST API: {exc}") from exc
        except ValueError as exc:
            raise ConnectionError("Failed to parse WebUntis REST timetable response as JSON.") from exc

        if isinstance(payload, list):
            page_items = payload
            pagination = {}
        else:
            page_items = payload.get("data") or payload.get("result") or payload.get("items") or payload.get("timetable") or []
            pagination = payload.get("pagination") or payload.get("page") or {}

        if not isinstance(page_items, list):
            raise ConnectionError("WebUntis REST timetable response did not contain a list of periods.")

        raw_periods.extend(page_items)

        has_next = False
        if isinstance(pagination, dict):
            if isinstance(pagination.get("hasNext"), bool):
                has_next = pagination["hasNext"]
            elif isinstance(pagination.get("nextPage"), int):
                has_next = pagination["nextPage"] > page
            elif isinstance(pagination.get("totalPages"), int):
                has_next = page < pagination["totalPages"]

        if not has_next:
            links = payload.get("links") if isinstance(payload, dict) else None
            if isinstance(links, dict) and links.get("next"):
                has_next = True

        if not has_next:
            break

        page += 1

    lessons = []
    for period in raw_periods:
        if not isinstance(period, dict):
            continue

        start_iso = _to_iso_minute(period.get("start") or period.get("startDateTime") or period.get("startTimeUtc"))
        end_iso = _to_iso_minute(period.get("end") or period.get("endDateTime") or period.get("endTimeUtc"))

        if not start_iso:
            start_iso = _from_date_and_time(period.get("date") or period.get("startDate"), period.get("startTime"))
        if not end_iso:
            end_iso = _from_date_and_time(period.get("date") or period.get("endDate") or period.get("startDate"), period.get("endTime"))

        period_subjects = _extract_names(period.get("subjects") or period.get("su"))
        period_teachers = _extract_names(period.get("teachers") or period.get("te"))
        period_rooms = _extract_names(period.get("rooms") or period.get("ro"))

        code_val = period.get("code")
        cell_state = str(period.get("cellState", "")).upper()
        is_cancelled = code_val == "cancelled" or cell_state in {"CANCEL", "CANCELLED"}

        if is_cancelled:
            code = "cancelled"
        elif code_val == "irregular" or cell_state in {"SUBST", "SHIFT", "IRREGULAR", "CHANGED"}:
            code = "irregular"
        else:
            code = None

        lessons.append({
            "id": period.get("id") or period.get("lessonId"),
            "start": start_iso,
            "end": end_iso,
            "subjects": period_subjects,
            "teachers": period_teachers,
            "rooms": period_rooms,
            "code": code,
            "change_type": _resolve_change_type(code, period_subjects),
        })

    lessons.sort(key=lambda l: (l["start"], str(l["id"]) if l["id"] is not None else ""))
    return lessons


def fetch(session: requests.Session | dict) -> list[dict]:
    if isinstance(session, dict) and session.get("mode") == "rest":
        token = session.get("token")
        if not isinstance(token, str) or not token:
            raise ConnectionError("REST session missing bearer token.")
        return fetch_rest(token)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    range_end = week_start + timedelta(days=DAYS_AHEAD)

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
                "endDate": range_end.strftime("%Y%m%d"),
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
    }, timeout=_REQUEST_TIMEOUT)
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
