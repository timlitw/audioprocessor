"""Add or edit one scheduled recording."""

import os
from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from core.job import Job
from core.probe import probe_stream

# Ordered for a US church audience; the box is editable for anything else.
COMMON_ZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
]


class JobDialog(QDialog):
    def __init__(self, job: Job, parent=None, title="Add Recording"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(620)
        self.job = job

        self._build_ui()
        self._load(job)
        self._refresh_preview()

    # --------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        root = QVBoxLayout()

        # --- stream -------------------------------------------------------
        stream_box = QGroupBox("Stream")
        stream_form = QFormLayout()

        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "http://us-az-phoenix-14.listentochurch.com:8000/1240536.mp3"
        )
        self.test_button = QPushButton("Test")
        self.test_button.setToolTip("Connect now and confirm the stream is reachable")
        self.test_button.clicked.connect(self._on_test)
        url_row.addWidget(self.url_edit)
        url_row.addWidget(self.test_button)
        stream_form.addRow("Stream URL:", url_row)

        # The URL identifies the Icecast server and account, not the church,
        # so the name has to be typed in.
        self.church_edit = QLineEdit()
        self.church_edit.setPlaceholderText(
            "Pleasant View Mennonite - used in the file name"
        )
        self.church_edit.textChanged.connect(self._refresh_preview)
        stream_form.addRow("Church:", self.church_edit)

        stream_box.setLayout(stream_form)
        root.addWidget(stream_box)

        # --- schedule -----------------------------------------------------
        sched_box = QGroupBox("When")
        sched_form = QFormLayout()

        time_row = QHBoxLayout()
        self.start_edit = QDateTimeEdit()
        self.start_edit.setDisplayFormat("yyyy-MM-dd   h:mm AP")
        self.start_edit.setCalendarPopup(True)
        self.start_edit.dateTimeChanged.connect(self._refresh_preview)

        self.tz_combo = QComboBox()
        self.tz_combo.setEditable(True)
        self.tz_combo.addItems(COMMON_ZONES)
        self.tz_combo.currentTextChanged.connect(self._refresh_preview)

        time_row.addWidget(self.start_edit, 2)
        time_row.addWidget(self.tz_combo, 2)
        sched_form.addRow("Service time:", time_row)

        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(0, 120)
        self.lead_spin.setSuffix(" min early")
        self.lead_spin.valueChanged.connect(self._refresh_preview)
        sched_form.addRow("Connect:", self.lead_spin)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 180)
        self.retry_spin.setSuffix(" min")
        self.retry_spin.setToolTip(
            "If the stream isn't up at the start time, keep trying this long\n"
            "before giving up. Covers a sound tech running late."
        )
        sched_form.addRow("Keep trying for:", self.retry_spin)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #888;")
        sched_form.addRow("", self.preview_label)

        sched_box.setLayout(sched_form)
        root.addWidget(sched_box)

        # --- stopping -----------------------------------------------------
        stop_box = QGroupBox("Stopping")
        stop_form = QFormLayout()

        dur_row = QHBoxLayout()
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 12)
        self.hours_spin.setSuffix(" h")
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setSuffix(" m")
        for spin in (self.hours_spin, self.minutes_spin):
            spin.valueChanged.connect(self._refresh_preview)
        dur_row.addWidget(self.hours_spin)
        dur_row.addWidget(self.minutes_spin)
        dur_row.addStretch()
        stop_form.addRow("Record at most:", dur_row)

        sil_row = QHBoxLayout()
        self.silence_check = QCheckBox("Stop after")
        self.silence_spin = QSpinBox()
        self.silence_spin.setRange(1, 120)
        self.silence_spin.setSuffix(" min of silence")
        self.silence_check.toggled.connect(self.silence_spin.setEnabled)
        self.silence_spin.valueChanged.connect(self._refresh_preview)
        sil_row.addWidget(self.silence_check)
        sil_row.addWidget(self.silence_spin)
        sil_row.addStretch()
        stop_form.addRow("", sil_row)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-90.0, -10.0)
        self.threshold_spin.setSingleStep(5.0)
        self.threshold_spin.setSuffix(" dB")
        self.threshold_spin.setToolTip(
            "Anything quieter than this counts as silence.\n"
            "Lower it if a noisy room keeps the recording alive."
        )
        stop_form.addRow("Silence level:", self.threshold_spin)

        self.silence_note = QLabel()
        self.silence_note.setWordWrap(True)
        self.silence_note.setStyleSheet("color: #888;")
        stop_form.addRow("", self.silence_note)

        stop_box.setLayout(stop_form)
        root.addWidget(stop_box)

        # --- output -------------------------------------------------------
        out_box = QGroupBox("Save to")
        out_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_browse)
        out_row.addWidget(self.folder_edit)
        out_row.addWidget(browse)
        out_box.setLayout(out_row)
        root.addWidget(out_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setLayout(root)

    # ------------------------------------------------------------- transfer

    def _load(self, job: Job) -> None:
        self.url_edit.setText(job.url)
        self.church_edit.setText(job.church)
        self.tz_combo.setCurrentText(job.timezone)
        self.lead_spin.setValue(job.lead_minutes)
        self.retry_spin.setValue(job.retry_minutes)
        self.hours_spin.setValue(job.max_seconds // 3600)
        self.minutes_spin.setValue((job.max_seconds % 3600) // 60)
        self.silence_check.setChecked(job.silence_minutes > 0)
        self.silence_spin.setValue(job.silence_minutes or 5)
        self.silence_spin.setEnabled(job.silence_minutes > 0)
        self.threshold_spin.setValue(job.threshold_db)
        self.folder_edit.setText(job.folder or default_folder())

        service = job.service_at()
        if service is not None:
            self.start_edit.setDateTime(QDateTime(service.replace(tzinfo=None)))
        else:
            self.start_edit.setDateTime(default_service_time())

    def result_job(self) -> Job:
        """The edited job. Only valid after the dialog is accepted."""
        job = self.job
        job.url = self.url_edit.text().strip()
        job.church = self.church_edit.text().strip()
        job.timezone = self.tz_combo.currentText().strip()
        job.lead_minutes = self.lead_spin.value()
        job.retry_minutes = self.retry_spin.value()
        job.max_seconds = self.hours_spin.value() * 3600 + self.minutes_spin.value() * 60
        job.silence_minutes = (
            self.silence_spin.value() if self.silence_check.isChecked() else 0
        )
        job.threshold_db = self.threshold_spin.value()
        job.folder = self.folder_edit.text().strip()
        job.service_time = self.start_edit.dateTime().toPyDateTime().isoformat(
            timespec="minutes"
        )
        return job

    # --------------------------------------------------------------- events

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Save recordings to", self.folder_edit.text()
        )
        if folder:
            self.folder_edit.setText(folder)

    def _on_test(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Stream Recorder", "Enter a stream URL first.")
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("...")
        try:
            result = probe_stream(url)
        finally:
            self.test_button.setEnabled(True)
            self.test_button.setText("Test")

        if result.ok:
            QMessageBox.information(
                self, "Stream Recorder", f"Stream is live.\n\n{result.detail}"
            )
        else:
            QMessageBox.critical(
                self, "Stream Recorder",
                f"Could not read that stream.\n\n{result.detail}",
            )

    def _on_accept(self) -> None:
        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "Stream Recorder", "Enter a stream URL.")
            return

        probe_job = Job(timezone=self.tz_combo.currentText().strip())
        if probe_job.zone() is None:
            QMessageBox.warning(
                self, "Stream Recorder",
                f"Unknown time zone: {self.tz_combo.currentText()!r}",
            )
            return

        if self.hours_spin.value() == 0 and self.minutes_spin.value() == 0:
            QMessageBox.warning(
                self, "Stream Recorder", "Set a maximum recording length."
            )
            return

        folder = self.folder_edit.text().strip()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self, "Stream Recorder", f"Cannot use that folder:\n{exc}"
            )
            return

        self.accept()

    # -------------------------------------------------------------- preview

    def _refresh_preview(self) -> None:
        job = Job(
            timezone=self.tz_combo.currentText().strip(),
            lead_minutes=self.lead_spin.value(),
            max_seconds=self.hours_spin.value() * 3600 + self.minutes_spin.value() * 60,
            service_time=self.start_edit.dateTime()
            .toPyDateTime()
            .isoformat(timespec="minutes"),
        )

        connect_at = job.connect_at()
        if connect_at is None:
            self.preview_label.setText(
                f"Unknown time zone: {self.tz_combo.currentText()!r}"
            )
        else:
            hard_stop = job.hard_stop_at()
            text = (
                f"Connects {pretty(connect_at)}  -  "
                f"your time {pretty(connect_at.astimezone())}\n"
                f"Hard stop at {pretty(hard_stop)} "
                f"({format_duration(job.max_seconds)} max)"
            )
            if connect_at < datetime.now(timezone.utc):
                text += "\nThat time has already passed."
            self.preview_label.setText(text)

        # A long meeting has breaks longer than the usual silence setting.
        note = (
            "The silence timer only starts once real audio has been heard, so "
            "the quiet before the service never stops the recording."
        )
        hours = job.max_seconds / 3600
        if hours >= 3 and self.silence_check.isChecked():
            if self.silence_spin.value() < 30:
                note += (
                    f"\n\nThis is a {format_duration(job.max_seconds)} recording, but "
                    f"it will stop after {self.silence_spin.value()} minutes of quiet. "
                    "A meal or a recess longer than that will end it early - "
                    "raise the silence setting above the longest break you expect."
                )
        self.silence_note.setText(note)


# ---------------------------------------------------------------- formatting


def pretty(moment: datetime) -> str:
    hour = moment.strftime("%I").lstrip("0") or "12"
    return moment.strftime(f"%a %b %d, {hour}:%M %p %Z")


def format_duration(seconds: int) -> str:
    hours, minutes = divmod(seconds // 60, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def default_service_time() -> QDateTime:
    """Tomorrow at 10:00 AM, or today if 10:00 hasn't happened yet."""
    now = datetime.now()
    target = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return QDateTime(target)


def default_folder() -> str:
    return os.path.join(os.path.expanduser("~"), "Recordings")
