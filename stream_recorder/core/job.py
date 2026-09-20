"""A scheduled recording, and the on-disk queue that outlives the app."""

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEDULED = "scheduled"
RECORDING = "recording"
DONE = "done"
FAILED = "failed"
MISSED = "missed"

# Statuses that still need the machine awake.
PENDING = (SCHEDULED, RECORDING)


@dataclass
class Job:
    """One church, one stream, one scheduled recording."""

    url: str = ""
    church: str = ""
    service_time: str = ""          # naive "2026-09-20T10:00", read in `timezone`
    timezone: str = "America/New_York"
    lead_minutes: int = 10
    max_seconds: int = 9000
    silence_minutes: int = 5        # 0 disables the silence rule
    threshold_db: float = -40.0
    retry_minutes: int = 30
    folder: str = ""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = SCHEDULED
    note: str = ""
    output_path: str = ""
    audio_start: float | None = None

    # ----------------------------------------------------------------- times

    def zone(self) -> ZoneInfo | None:
        try:
            return ZoneInfo(self.timezone.strip())
        except (ZoneInfoNotFoundError, ValueError, ModuleNotFoundError):
            return None

    def service_at(self) -> datetime | None:
        """Service start, in the church's own time zone."""
        zone = self.zone()
        if zone is None or not self.service_time:
            return None
        try:
            naive = datetime.fromisoformat(self.service_time)
        except ValueError:
            return None
        return naive.replace(tzinfo=zone)

    def connect_at(self) -> datetime | None:
        """When recording should begin - the head start before the service."""
        service = self.service_at()
        if service is None:
            return None
        return service - timedelta(minutes=self.lead_minutes)

    def hard_stop_at(self) -> datetime | None:
        connect = self.connect_at()
        if connect is None:
            return None
        return connect + timedelta(seconds=self.max_seconds)

    # ---------------------------------------------------------------- naming

    def display_name(self) -> str:
        return self.church.strip() or _host(self.url) or "(no name)"


# --------------------------------------------------------------------- store


def store_path() -> str:
    """Where the queue lives between runs."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "StreamRecorder", "jobs.json")


def load_jobs() -> list[Job]:
    """Read the saved queue. A missing or damaged file just means no jobs."""
    path = store_path()
    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list):
        return []

    fields = {f for f in Job.__dataclass_fields__}
    jobs = []
    for entry in raw:
        if isinstance(entry, dict):
            jobs.append(Job(**{k: v for k, v in entry.items() if k in fields}))
    return jobs


def save_jobs(jobs: list[Job]) -> None:
    """Write the queue atomically so a crash mid-write can't lose it."""
    path = store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"

    with open(temp, "w", encoding="utf-8") as fh:
        json.dump([asdict(job) for job in jobs], fh, indent=2)
    os.replace(temp, path)


def _host(url: str) -> str:
    try:
        return url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
    except IndexError:
        return ""
