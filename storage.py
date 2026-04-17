"""
storage.py – Persist the last known timetable to disk so the bot survives restarts.
"""

import json
import os
from pathlib import Path

_FILE = Path("last_timetable.json")


def save(tt: list[dict]) -> None:
    """Write the timetable to disk as JSON using an atomic file replace."""
    temp_file = _FILE.with_suffix(".tmp.json")
    temp_file.write_text(json.dumps(tt, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_file, _FILE)


def load() -> list[dict] | None:
    """
    Read the timetable from disk.
    Returns None if no persisted snapshot exists yet.
    """
    if not _FILE.exists():
        return None
    return json.loads(_FILE.read_text(encoding="utf-8"))
