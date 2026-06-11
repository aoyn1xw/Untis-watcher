"""
storage.py – Persist watcher state to disk so the bot survives restarts.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STATE_FILE = Path("state.json")
_LEGACY_TIMETABLE_FILE = Path("last_timetable.json")
_STATE_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state() -> dict[str, Any] | None:
    """
    Read the full watcher state from disk.
    Returns None if no persisted state exists yet.
    """
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))

    # One-time compatibility for users upgrading from last_timetable.json.
    # The next successful fetch writes state.json and becomes the source of truth.
    if _LEGACY_TIMETABLE_FILE.exists():
        timetable = json.loads(_LEGACY_TIMETABLE_FILE.read_text(encoding="utf-8"))
        if isinstance(timetable, list):
            return {
                "version": _STATE_VERSION,
                "updated_at": None,
                "timetable": timetable,
                "source": "legacy:last_timetable.json",
            }

    return None


def save_state(timetable: list[dict]) -> None:
    """Write the latest fetched WebUntis data to state.json using an atomic replace."""
    state = {
        "version": _STATE_VERSION,
        "updated_at": _utc_now_iso(),
        "timetable": timetable,
    }
    temp_file = _STATE_FILE.with_suffix(".tmp.json")
    temp_file.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_file, _STATE_FILE)


def load() -> list[dict] | None:
    """
    Backwards-compatible helper that returns only the persisted timetable.
    New code should call load_state() so metadata remains available.
    """
    state = load_state()
    if not state:
        return None

    timetable = state.get("timetable")
    return timetable if isinstance(timetable, list) else None


def save(tt: list[dict]) -> None:
    """
    Backwards-compatible helper that persists a timetable into state.json.
    New code should call save_state().
    """
    save_state(tt)
