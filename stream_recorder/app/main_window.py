"""Stream Recorder - schedule church streams, record them, stop when they go quiet."""

import os
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.job_dialog import JobDialog, default_folder, format_duration, pretty
from core.job import (
    DONE, FAILED, MISSED, PENDING, RECORDING, SCHEDULED, Job, load_jobs, save_jobs,
)
from core.power import KeepAwake
from core.recorder import Recorder, RecordingJob, clock

COLUMNS = ["Church", "Stream", "Starts", "Max", "Status"]

STATUS_COLORS = {
    RECORDING: QColor("#2e7d32"),
    FAILED: QColor("#c62828"),
    MISSED: QColor("#ef6c00"),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stream Recorder")
        self.resize(940, 620)

        self.keep_awake = KeepAwake()
        self.jobs: list[Job] = []
        self.active: dict[str, Recorder] = {}
        self.live: dict[str, str] = {}      # job id -> live status text

        self._build_ui()
        self._restore_queue()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

    # --------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        root = QVBoxLayout()

        heading = QLabel("Scheduled Recordings")
        heading.setStyleSheet("font-size: 15px; font-weight: bold;")
        root.addWidget(heading)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_edit)
        self.table.itemSelectionChanged.connect(self._refresh_buttons)

        header = self.table.horizontalHeader()
        for index in range(len(COLUMNS)):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if COLUMNS[index] == "Status"
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(index, mode)
        root.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self._on_add)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._on_remove)
        self.start_button = QPushButton("Start Now")
        self.start_button.clicked.connect(self._on_start_now)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._on_stop)

        for button in (self.add_button, self.edit_button, self.remove_button):
            button.setMinimumHeight(32)
            button_row.addWidget(button)
        button_row.addStretch()
        for button in (self.start_button, self.stop_button):
            button.setMinimumHeight(32)
            button_row.addWidget(button)
        root.addLayout(button_row)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #888;")
        root.addWidget(self.summary_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setMinimumHeight(150)
        root.addWidget(self.log_view)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)
        self._refresh_buttons()

    # ---------------------------------------------------------------- queue

    def _restore_queue(self) -> None:
        self.jobs = load_jobs()

        # Anything that should have run while the app was shut is reported,
        # not started late behind your back.
        now = datetime.now(timezone.utc)
        for job in self.jobs:
            if job.status == RECORDING:
                job.status = FAILED
                job.note = "interrupted - the app closed mid-recording"
            elif job.status == SCHEDULED:
                connect_at = job.connect_at()
                if connect_at is not None and connect_at < now:
                    job.status = MISSED
                    job.note = "missed while the app was closed"

        if self.jobs:
            self._log(f"Loaded {len(self.jobs)} saved recording(s).")
        self._rebuild_table()
        self._save()

    def _save(self) -> None:
        try:
            save_jobs(self.jobs)
        except OSError as exc:
            self._log(f"Could not save the queue: {exc}")

    def _selected(self) -> Job | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        if 0 <= index < len(self.jobs):
            return self.jobs[index]
        return None

    # ----------------------------------------------------------------- table

    def _rebuild_table(self) -> None:
        selected = self._selected()
        self.table.setRowCount(len(self.jobs))

        for row, job in enumerate(self.jobs):
            connect_at = job.connect_at()
            starts = pretty(connect_at) if connect_at else "(bad time zone)"

            values = [
                job.display_name(),
                _host(job.url),
                starts,
                format_duration(job.max_seconds),
                "",
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 1:
                    item.setToolTip(job.url)
                self.table.setItem(row, column, item)

        self._refresh_status_cells()

        if selected is not None:
            for row, job in enumerate(self.jobs):
                if job.id == selected.id:
                    self.table.selectRow(row)
                    break
        self._refresh_buttons()

    def _refresh_status_cells(self) -> None:
        """Called every second - this is the live per-stream status."""
        now = datetime.now(timezone.utc)

        for row, job in enumerate(self.jobs):
            item = self.table.item(row, len(COLUMNS) - 1)
            if item is None:
                continue
            item.setText(self._status_text(job, now))
            color = STATUS_COLORS.get(job.status)
            if color is not None:
                item.setForeground(color)

        pending = sum(1 for job in self.jobs if job.status in PENDING)
        recording = len(self.active)
        if pending:
            self.summary_label.setText(
                f"{recording} recording, {pending - recording} waiting "
                f"- this machine will not sleep."
            )
        else:
            self.summary_label.setText("Nothing scheduled.")

    def _status_text(self, job: Job, now: datetime) -> str:
        if job.status == RECORDING:
            return self.live.get(job.id, "Recording...")

        if job.status == SCHEDULED:
            connect_at = job.connect_at()
            if connect_at is None:
                return "Bad time zone - edit this job"
            remaining = (connect_at - now).total_seconds()
            if remaining <= 0:
                return "Starting..."
            return f"Waiting - starts in {_countdown(remaining)}"

        return job.note or job.status

    def _refresh_buttons(self) -> None:
        job = self._selected()
        running = job is not None and job.id in self.active

        self.edit_button.setEnabled(job is not None and not running)
        self.remove_button.setEnabled(job is not None)
        self.start_button.setEnabled(job is not None and not running)
        self.stop_button.setEnabled(running)

    # --------------------------------------------------------------- actions

    def _on_add(self) -> None:
        template = Job(folder=default_folder())
        if self.jobs:
            # Carry the last job's settings forward - the next church usually
            # wants the same shape of recording.
            last = self.jobs[-1]
            template.folder = last.folder
            template.timezone = last.timezone
            template.lead_minutes = last.lead_minutes
            template.max_seconds = last.max_seconds
            template.silence_minutes = last.silence_minutes
            template.threshold_db = last.threshold_db
            template.retry_minutes = last.retry_minutes

        dialog = JobDialog(template, self, "Add Recording")
        if dialog.exec():
            job = dialog.result_job()
            self.jobs.append(job)
            self._log(f"Added {job.display_name()} - {pretty(job.connect_at())}")
            self._rebuild_table()
            self._save()

    def _on_edit(self) -> None:
        job = self._selected()
        if job is None or job.id in self.active:
            return

        dialog = JobDialog(job, self, f"Edit {job.display_name()}")
        if dialog.exec():
            edited = dialog.result_job()
            if edited.status in (MISSED, FAILED, DONE):
                edited.status = SCHEDULED
                edited.note = ""
            self._log(f"Updated {edited.display_name()}")
            self._rebuild_table()
            self._save()

    def _on_remove(self) -> None:
        job = self._selected()
        if job is None:
            return

        if job.id in self.active:
            answer = QMessageBox.question(
                self, "Stream Recorder",
                f"{job.display_name()} is recording right now.\n\n"
                "Stop it and remove it from the list?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.active[job.id].request_stop("stopped - removed from the list")

        self.jobs = [existing for existing in self.jobs if existing.id != job.id]
        self._log(f"Removed {job.display_name()}")
        self._rebuild_table()
        self._save()

    def _on_start_now(self) -> None:
        job = self._selected()
        if job is None or job.id in self.active:
            return

        if job.status in (DONE, FAILED, MISSED):
            answer = QMessageBox.question(
                self, "Stream Recorder",
                f"Start recording {job.display_name()} now?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._begin(job)

    def _on_stop(self) -> None:
        job = self._selected()
        if job is None:
            return
        recorder = self.active.get(job.id)
        if recorder is not None:
            self._log(f"{job.display_name()}: stopping...")
            recorder.request_stop()

    # ------------------------------------------------------------- scheduler

    def _on_tick(self) -> None:
        now = datetime.now(timezone.utc)

        for job in self.jobs:
            if job.status != SCHEDULED or job.id in self.active:
                continue
            connect_at = job.connect_at()
            if connect_at is not None and now >= connect_at:
                self._begin(job)

        self._refresh_status_cells()

    def _begin(self, job: Job) -> None:
        job.status = RECORDING
        job.note = ""
        job.audio_start = None
        job.output_path = self._output_path(job)
        self.live[job.id] = "Connecting..."

        recording = RecordingJob(
            url=job.url,
            output_path=job.output_path,
            max_seconds=job.max_seconds,
            silence_limit_seconds=job.silence_minutes * 60,
            silence_threshold_db=job.threshold_db,
            retry_seconds=job.retry_minutes * 60,
        )

        name = job.display_name()
        self._log(f"{name}: recording to {job.output_path}")

        recorder = Recorder(recording, self)
        job_id = job.id
        recorder.log.connect(lambda text, n=name: self._log(f"{n}: {text}"))
        recorder.status.connect(lambda text, i=job_id: self._on_status(i, text))
        recorder.audio_detected.connect(lambda at, i=job_id: self._on_audio(i, at))
        recorder.progress.connect(lambda at, i=job_id: self._on_progress(i, at))
        recorder.done.connect(
            lambda reason, path, i=job_id: self._on_done(i, reason, path)
        )

        self.active[job.id] = recorder
        self.keep_awake.hold()
        recorder.start()

        self._rebuild_table()
        self._save()

    # -------------------------------------------------------- recorder events

    def _on_status(self, job_id: str, text: str) -> None:
        self.live[job_id] = text
        self._refresh_status_cells()

    def _on_audio(self, job_id: str, stream_seconds: float) -> None:
        job = self._job(job_id)
        if job is not None:
            job.audio_start = stream_seconds

    def _on_progress(self, job_id: str, stream_seconds: float) -> None:
        job = self._job(job_id)
        if job is None:
            return
        text = f"Recording {clock(stream_seconds)}"
        if job.audio_start is not None:
            text += f"  -  audio began at {clock(job.audio_start)}"
        else:
            text += "  -  waiting for audio"
        self.live[job_id] = text

    def _on_done(self, job_id: str, reason: str, path: str) -> None:
        self.active.pop(job_id, None)
        self.live.pop(job_id, None)

        job = self._job(job_id)
        if job is not None:
            name = job.display_name()
            if reason.startswith("error:"):
                detail = reason[6:].strip()
                job.status = FAILED
                job.note = f"Failed - {detail}"
                self._log(f"{name}: failed - {detail}")
            else:
                size_mb = 0.0
                if path and os.path.exists(path):
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                job.status = DONE
                if job.audio_start is not None:
                    job.note = (
                        f"Done - audio starts at {clock(job.audio_start)} "
                        f"- {size_mb:.1f} MB"
                    )
                    self._log(
                        f"{name}: finished - {reason}. {size_mb:.1f} MB. "
                        f"Trim point: audio starts {clock(job.audio_start)} into the file."
                    )
                else:
                    job.note = f"Done - no audio detected - {size_mb:.1f} MB"
                    self._log(
                        f"{name}: finished - {reason}. "
                        "No audio was ever detected on this stream."
                    )

        if not self.active and not any(j.status in PENDING for j in self.jobs):
            self.keep_awake.release()

        self._rebuild_table()
        self._save()

    # --------------------------------------------------------------- helpers

    def _job(self, job_id: str) -> Job | None:
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def _output_path(self, job: Job) -> str:
        folder = job.folder or default_folder()
        os.makedirs(folder, exist_ok=True)

        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        name = _safe_name(job.church) or "recording"
        path = os.path.join(folder, f"{name}_{stamp}.mp3")

        # Two churches can start at the same minute; never overwrite.
        counter = 2
        while os.path.exists(path):
            path = os.path.join(folder, f"{name}_{stamp}-{counter}.mp3")
            counter += 1
        return path

    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"{stamp}  {message}")

    def closeEvent(self, event) -> None:
        if self.active:
            answer = QMessageBox.question(
                self, "Stream Recorder",
                f"{len(self.active)} recording(s) still running.\n\n"
                "Stop them and close?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for recorder in list(self.active.values()):
                recorder.request_stop("stopped - app closed")
            for recorder in list(self.active.values()):
                recorder.wait(5000)

        self.keep_awake.release()
        self._save()
        event.accept()


# ---------------------------------------------------------------- formatting


def _countdown(seconds: float) -> str:
    total = int(seconds)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _safe_name(text: str) -> str:
    cleaned = "".join(c for c in text if c.isalnum() or c in " _-").strip()
    return "-".join(cleaned.split())


def _host(url: str) -> str:
    try:
        return url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
    except IndexError:
        return url
