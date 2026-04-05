"""Settings persistence for Transcription Studio."""

import json
from pathlib import Path

SETTINGS_DIR = Path.home() / ".transcription_studio"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
MAX_RECENT_PROJECTS = 15


def _ensure_dir():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    _ensure_dir()
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_settings(settings: dict) -> None:
    _ensure_dir()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def get_recent_projects() -> list[str]:
    settings = load_settings()
    paths = settings.get("recent_projects", [])
    return [p for p in paths if Path(p).exists()]


def add_recent_project(project_path: str) -> None:
    settings = load_settings()
    paths = settings.get("recent_projects", [])
    abs_path = str(Path(project_path).resolve())
    paths = [p for p in paths if p != abs_path]
    paths.insert(0, abs_path)
    paths = paths[:MAX_RECENT_PROJECTS]
    settings["recent_projects"] = paths
    save_settings(settings)


def get_last_directory() -> str:
    return load_settings().get("last_directory", "")


def set_last_directory(directory: str) -> None:
    settings = load_settings()
    settings["last_directory"] = directory
    save_settings(settings)


def get_whisper_model() -> str:
    return load_settings().get("whisper_model", "base")


def set_whisper_model(model: str) -> None:
    settings = load_settings()
    settings["whisper_model"] = model
    save_settings(settings)
