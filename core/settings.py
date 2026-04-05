"""Settings persistence — recent files and user preferences."""

import json
from pathlib import Path
from PyQt6.QtCore import QSettings


SETTINGS_DIR = Path.home() / ".audio_processor"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
MAX_RECENT_FILES = 15


def _ensure_dir():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    """Load settings from JSON file."""
    _ensure_dir()
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_settings(settings: dict) -> None:
    """Save settings to JSON file."""
    _ensure_dir()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def get_recent_files() -> list[str]:
    """Get list of recent file paths."""
    settings = load_settings()
    files = settings.get("recent_files", [])
    # Filter out files that no longer exist
    return [f for f in files if Path(f).exists()]


def add_recent_file(file_path: str) -> None:
    """Add a file to the recent files list."""
    settings = load_settings()
    files = settings.get("recent_files", [])

    # Remove if already present, then add to front
    abs_path = str(Path(file_path).resolve())
    files = [f for f in files if f != abs_path]
    files.insert(0, abs_path)
    files = files[:MAX_RECENT_FILES]

    settings["recent_files"] = files
    save_settings(settings)


def get_last_directory() -> str:
    """Get the last directory used for file dialogs."""
    settings = load_settings()
    return settings.get("last_directory", "")


def set_last_directory(directory: str) -> None:
    """Save the last used directory."""
    settings = load_settings()
    settings["last_directory"] = directory
    save_settings(settings)


def get_last_bitrate() -> str:
    settings = load_settings()
    return settings.get("last_bitrate", "192k")


def set_last_bitrate(bitrate: str) -> None:
    settings = load_settings()
    settings["last_bitrate"] = bitrate
    save_settings(settings)
