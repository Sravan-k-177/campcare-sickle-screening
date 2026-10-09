"""App-directory-anchored paths + persistent JSON settings.

Everything the camp needs across restarts lives next to the app:
  camp_screenings.db  - all patients, vitals, AI screenings (SQLite)
  camp_settings.json  - camp profile + AI threshold (JSON)

Paths are anchored to this file's location so launching the app from any
working directory always opens the SAME database and settings.
"""

from __future__ import annotations

import json
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.environ.get("CAMP_DB", os.path.join(APP_DIR, "camp_screenings.db"))
SETTINGS_FILE = os.path.join(APP_DIR, "camp_settings.json")

DEFAULT_SETTINGS = {
    "camp": "Village Health Camp",
    "site": "",
    "operator": "",
    "date": "",
    "ai_threshold": None,
}


def load_settings() -> dict:
    """Read persisted settings; fall back to defaults on first run."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            settings.update({k: stored.get(k, v) for k, v in DEFAULT_SETTINGS.items()})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return settings


def save_settings(patch: dict) -> dict:
    """Merge a patch into the JSON file and return the full settings."""
    settings = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in patch:
            settings[key] = patch[key]
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
    return settings
