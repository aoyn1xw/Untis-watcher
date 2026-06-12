"""
timetable.py – Connect to WebUntis and fetch the upcoming timetable.
Uses WebUntis JSON-RPC by default, with optional official REST API support.
"""

import base64
import logging
import time
from datetime import date, timedelta
from typing import Any

import requests

from config import (
    DAYS_AHEAD,
    UNTIS_API_PASSWORD,
    UNTIS_CLIENT_ID,
    UNTIS_ELEMENT_ID,
    UNTIS_ELEMENT_TYPE,
    UNTIS_PASSWORD,
    UNTIS_SCHOOL,
    UNTIS_SERVER,
    UNTIS_TENANT_ID,
    UNTIS_USER,
)

logger = logging.getLogger("untis-watcher")

# Keywords in subject names that indicate an exam period
_EXAM_KEYWORDS = ("prüfung", "klausur", "test", "pruefung")

# Element type constants used by WebUntis timetable elements
_TYPE_TEACHER = 2
_TYPE_SUBJECT = 3
_TYPE_ROOM = 4
# requests timeout: (connect_timeout_seconds, read_timeout_seconds)
_REQUEST_TIMEOUT = (10, 30)
_REST_TOKEN_URL = "https://api.webuntis.com/WebUntis/api/sso/v3/{tenant_id}/token?grant_type=client_credentials"
_REST_TIMETABLE_URL = "https://api.webuntis.com/WebUntis/api/rest/extern/v3/timetable"
_TOKEN_EXPIRY_SAFETY_SECONDS = 15
_JSONRPC_PATH = "/WebUntis/jsonrpc.do"
_CLIENT_IDENTITY = "untis-watcher"

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


def _school_cookie_value() -> str:
    """Return the WebUntis schoolname cookie value used by its web client."""
    encoded_school = base64.b64encode(UNTIS_SCHOOL.encode("utf-8")).decode("ascii")
    return f"_{encoded_school}"


def _jsonrpc_url() -> str:
    return f"https://{UNTIS_SERVER}{_JSONRPC_PATH}"


def _jsonrpc_request(
    session: requests.Session,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: str | int | None = None,
) -> Any:
    """Call the WebUntis JSON-RPC endpoint and return the result payload."""
    response = session.post(
        session._untis_url,
        params={"school": UNTIS_SCHOOL},
        json={
            "id": request_id or str(int(time.time() * 1000)),
            "method": method,
            "params": params or {},
            "jsonrpc": "2.0",
        },
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise ConnectionError(f"WebUntis {method} response was not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ConnectionError(f"WebUntis {method} response had an unexpected shape.")
    if "error" in payload:
        raise ConnectionError(f"WebUntis {method} failed: {payload['error']}")
    if "result" not in payload:
        raise ConnectionError(f"WebUntis {method} failed: missing result payload.")
    return payload["result"]


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


def _extract_names(value: Any, lookup: dict[int, str] | None = None) -> list[str]:
    if value is None:
        return []

    entries = value if isinstance(value, list) else [value]
    names: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            if entry:
                names.append(entry)
            continue

        if not isinstance(entry, dict):
            continue

        entry_id = entry.get("id")
        if lookup and entry_id in lookup:
            names.append(lookup[entry_id])
            continue

        for key in ("name", "longname", "longName", "displayName", "fullName", "shortName", "code", "label"):
            candidate = entry.get(key)
            if isinstance(candidate, str) and candidate:
                names.append(candidate)
                break

    return names


def _lookup_by_id(items: Any) -> dict[int, str]:
    if not isinstance(items, list):
        return {}

    lookup: dict[int, str] = {}
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            continue
        name = item.get("name") or item.get("longname") or item.get("longName")
        if name:
            lookup[item["id"]] = str(name)
    return lookup


def _resolve_change_type(code: str | None, subjects: list[str]) -> str:
    subject_lower = " ".join(subjects).lower()
    if any(kw in subject_lower for kw in _EXAM_KEYWORDS):
        return "exam"
    if code == "cancelled":
        return "cancelled"
    if code == "irregular":
        return "changed"
    return "normal"


def _normalise_period(
    period: dict[str, Any],
    *,
    subject_lookup: dict[int, str] | None = None,
    teacher_lookup: dict[int, str] | None = None,
    room_lookup: dict[int, str] | None = None,
) -> dict[str, Any]:
    start_iso = _to_iso_minute(period.get("start") or period.get("startDateTime") or period.get("startTimeUtc"))
    end_iso = _to_iso_minute(period.get("end") or period.get("endDateTime") or period.get("endTimeUtc"))

    if not start_iso:
        start_iso = _from_date_and_time(period.get("date") or period.get("startDate"), period.get("startTime"))
    if not end_iso:
        end_iso = _from_date_and_time(period.get("date") or period.get("endDate") or period.get("startDate"), period.get("endTime"))

    period_subjects = _extract_names(period.get("subjects") or period.get("su"), subject_lookup)
    period_teachers = _extract_names(period.get("teachers") or period.get("te"), teacher_lookup)
    period_rooms = _extract_names(period.get("rooms") or period.get("ro"), room_lookup)

    code_val = period.get("code")
    cell_state = str(period.get("cellState", "")).upper()
    is_cancelled = code_val == "cancelled" or cell_state in {"CANCEL", "CANCELLED"}

    if is_cancelled:
        code = "cancelled"
    elif code_val == "irregular" or cell_state in {"SUBST", "SHIFT", "IRREGULAR", "CHANGED"}:
        code = "irregular"
    else:
        code = None

    return {
        "id": period.get("id") or period.get("lessonId"),
        "start": start_iso,
        "end": end_iso,
        "subjects": period_subjects,
        "teachers": period_teachers,
        "rooms": period_rooms,
        "code": code,
        "change_type": _resolve_change_type(code, period_subjects),
    }


def get_bearer_token() -> str:
    """Return a cached bearer token for WebUntis REST API or refresh when expired."""
    now = time.time()
    cached_token = _token_cache.get("access_token")
    cached_expiry = float(_token_cache.get("expires_at") or 0)
    if isinstance(cached_token, str) and cached_token and now < (cached_expiry - _TOKEN_EXPIRY_SAFETY_SECONDS):
        logger.debug("[untis] Using cached REST bearer token (expires in %.0fs).",
                     cached_expiry - now)
        return cached_token

    if not (UNTIS_TENANT_ID and UNTIS_CLIENT_ID and UNTIS_API_PASSWORD):
        raise ConnectionError("REST token request requires UNTIS_TENANT_ID, UNTIS_CLIENT_ID, and UNTIS_API_PASSWORD.")

    logger.info("[untis] Requesting new REST bearer token for tenant '%s'.", UNTIS_TENANT_ID)
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
    logger.info("[untis] REST bearer token obtained (expires in %ds).", expires_in_seconds)
    return token


def get_session() -> requests.Session | dict:
    """Open a WebUntis session via REST credentials or JSON-RPC user/password login."""
    use_rest, missing_rest = _rest_creds_status()
    if not use_rest and missing_rest and any([UNTIS_TENANT_ID, UNTIS_CLIENT_ID, UNTIS_API_PASSWORD]):
        raise ConnectionError(
            "Incomplete REST credentials. Set all of UNTIS_TENANT_ID, UNTIS_CLIENT_ID, UNTIS_API_PASSWORD. "
            f"Missing: {', '.join(missing_rest)}"
        )

    if use_rest:
        logger.info("[untis] Authenticating via REST API (tenant: %s).", UNTIS_TENANT_ID)
        return {
            "mode": "rest",
            "token": get_bearer_token(),
        }

    logger.info("[untis] Authenticating via JSON-RPC as user '%s' on %s (school: %s).",
                UNTIS_USER, UNTIS_SERVER, UNTIS_SCHOOL)

    session = requests.Session()
    session._untis_url = _jsonrpc_url()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Requested-With": "XMLHttpRequest",
    })

    result = _jsonrpc_request(
        session,
        "authenticate",
        {
            "user": UNTIS_USER,
            "password": UNTIS_PASSWORD,
            "client": _CLIENT_IDENTITY,
        },
        request_id="login",
    )

    if not isinstance(result, dict):
        raise ConnectionError("WebUntis login failed: unexpected authentication response shape.")

    session_id = result.get("sessionId")
    if not session_id:
        raise ConnectionError("WebUntis login failed: no session ID returned.")
    if result.get("code"):
        raise ConnectionError(f"WebUntis login failed with code: {result['code']}")

    session._session_id = session_id
    session._person_id = result.get("personId", UNTIS_ELEMENT_ID)
    session._person_type = result.get("personType", UNTIS_ELEMENT_TYPE)
    session.cookies.set("JSESSIONID", session_id)
    session.cookies.set("schoolname", _school_cookie_value())

    logger.info("[untis] JSON-RPC session opened (personId=%s, personType=%s).",
                session._person_id, session._person_type)
    return session


def validate_session(session: requests.Session | dict) -> bool:
    """Return whether the current WebUntis session is still accepted."""
    if isinstance(session, dict) and session.get("mode") == "rest":
        return bool(session.get("token"))

    try:
        return isinstance(_jsonrpc_request(session, "getLatestImportTime", request_id="validate"), int)
    except Exception:
        return False


def logout(session: requests.Session | dict) -> None:
    """Log out of WebUntis."""
    if isinstance(session, dict) and session.get("mode") == "rest":
        return

    try:
        _jsonrpc_request(session, "logout", request_id="logout")
        logger.debug("[untis] JSON-RPC session logged out.")
    except Exception:
        pass  # best-effort logout


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
        logger.debug("[untis] REST page %d: received %d period(s).", page, len(page_items))

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

    lessons = [_normalise_period(period) for period in raw_periods if isinstance(period, dict)]
    lessons.sort(key=lambda lesson: (lesson["start"], str(lesson["id"]) if lesson["id"] is not None else ""))
    return lessons


def fetch(session: requests.Session | dict) -> list[dict]:
    if isinstance(session, dict) and session.get("mode") == "rest":
        token = session.get("token")
        if not isinstance(token, str) or not token:
            raise ConnectionError("REST session missing bearer token.")
        return fetch_rest(token)

    if not validate_session(session):
        raise ConnectionError("WebUntis session is no longer valid.")

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    range_end = week_start + timedelta(days=DAYS_AHEAD)

    logger.info("[untis] Fetching timetable for element %s (type %s), %s to %s (%d days ahead).",
                session._person_id, session._person_type,
                week_start.isoformat(), range_end.isoformat(), DAYS_AHEAD)

    result = _jsonrpc_request(
        session,
        "getTimetable",
        {
            "options": {
                "id": int(time.time() * 1000),
                "element": {
                    "id": session._person_id,
                    "type": session._person_type,
                },
                "startDate": week_start.strftime("%Y%m%d"),
                "endDate": range_end.strftime("%Y%m%d"),
                "showInfo": True,
                "showSubstText": True,
                "showLsText": True,
                "showLsNumber": True,
                "showStudentgroup": True,
                "showBooking": True,
                "klasseFields": ["id", "name", "longname", "externalkey"],
                "roomFields": ["id", "name", "longname", "externalkey"],
                "subjectFields": ["id", "name", "longname", "externalkey"],
                "teacherFields": ["id", "name", "longname", "externalkey"],
            }
        },
        request_id="timetable",
    )

    if isinstance(result, list):
        periods = result
        subjects = {}
        teachers = {}
        rooms = {}
    elif isinstance(result, dict):
        periods = result.get("result") or result.get("data") or result.get("timetable") or []
        subjects = _lookup_by_id(result.get("subjects"))
        teachers = _lookup_by_id(result.get("teachers"))
        rooms = _lookup_by_id(result.get("rooms"))
    else:
        raise ConnectionError("WebUntis timetable response had an unexpected shape.")

    if not isinstance(periods, list):
        raise ConnectionError("WebUntis timetable response did not contain a list of periods.")

    lessons = [
        _normalise_period(period, subject_lookup=subjects, teacher_lookup=teachers, room_lookup=rooms)
        for period in periods
        if isinstance(period, dict)
    ]
    lessons.sort(key=lambda lesson: (lesson["start"], str(lesson["id"]) if lesson["id"] is not None else ""))
    logger.info("[untis] Timetable fetched: %d raw period(s) normalised to %d lesson(s).",
                len(periods), len(lessons))
    return lessons
