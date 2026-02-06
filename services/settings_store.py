"""Persists customization settings to a local JSON file so they carry over between sessions."""

import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "saved_settings.json")

DEFAULTS = {
    "title": "Sermon BINGO",
    "church_name": "",
    "header_color": "#2c3e50",
    "border_color": "#34495e",
    "date": "",
    "footer_message": "",
}

# Keys that get persisted (logo is handled separately since it's a file)
PERSISTED_KEYS = ["title", "church_name", "header_color", "border_color", "footer_message"]


def load_settings():
    """Load saved settings from disk, merged with defaults."""
    settings = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt file — just use defaults
    return settings


def save_settings(data):
    """Save the persistable customization settings to disk."""
    to_save = {k: data.get(k, DEFAULTS.get(k, "")) for k in PERSISTED_KEYS}
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)
    except OSError:
        pass  # If we can't write, silently continue
