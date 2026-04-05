"""Noise reduction dialog — capture profile, adjust strength, apply."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QDoubleSpinBox, QCheckBox, QGroupBox, QComboBox,
)
from PyQt6.QtCore import Qt

DIALOG_STYLE = """
    QDialog { background: #2b2b2b; color: #d0d0d0; }
    QGroupBox { border: 1px solid #555; border-radius: 4px; margin-top: 8px; padding-top: 12px; color: #d0d0d0; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; }
    QDoubleSpinBox, QComboBox { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; padding: 4px; }
    QSlider::groove:horizontal { background: #3a3a3a; height: 6px; border-radius: 3px; }
    QSlider::handle:horizontal { background: #00cc44; width: 14px; margin: -4px 0; border-radius: 7px; }
    QPushButton { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; border-radius: 3px; padding: 4px 16px; }
    QPushButton:hover { background: #4a4a4a; }
    QCheckBox { color: #d0d0d0; }
"""


class NoiseReductionDialog(QDialog):
    def __init__(self, has_profile: bool = False, has_selection: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Noise Reduction")
        self.setFixedSize(400, 350)

        self.strength = 2.0
        self.floor = 0.02
        self.remove_hum = False
        self.hum_freq = 60.0
        self.capture_profile = False
        self.apply_reduction = False

        layout = QVBoxLayout(self)

        # Profile section
        profile_group = QGroupBox("Noise Profile")
        profile_layout = QVBoxLayout(profile_group)

        status = "Profile captured" if has_profile else "No profile — select a noise-only region first"
        self.profile_status = QLabel(status)
        profile_layout.addWidget(self.profile_status)

        self.btn_capture = QPushButton("Capture Noise Profile from Selection")
        self.btn_capture.setEnabled(has_selection)
        self.btn_capture.clicked.connect(self._on_capture)
        profile_layout.addWidget(self.btn_capture)

        layout.addWidget(profile_group)

        # Settings section
        settings_group = QGroupBox("Reduction Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Strength slider
        str_row = QHBoxLayout()
        str_row.addWidget(QLabel("Strength:"))
        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(5, 50)
        self.strength_slider.setValue(20)
        self.strength_slider.setTickInterval(5)
        str_row.addWidget(self.strength_slider)
        self.strength_label = QLabel("2.0")
        str_row.addWidget(self.strength_label)
        self.strength_slider.valueChanged.connect(
            lambda v: self.strength_label.setText(f"{v / 10:.1f}")
        )
        settings_layout.addLayout(str_row)

        # Floor slider
        floor_row = QHBoxLayout()
        floor_row.addWidget(QLabel("Floor:"))
        self.floor_slider = QSlider(Qt.Orientation.Horizontal)
        self.floor_slider.setRange(1, 20)
        self.floor_slider.setValue(2)
        floor_row.addWidget(self.floor_slider)
        self.floor_label = QLabel("0.02")
        floor_row.addWidget(self.floor_label)
        self.floor_slider.valueChanged.connect(
            lambda v: self.floor_label.setText(f"{v / 100:.2f}")
        )
        settings_layout.addLayout(floor_row)

        layout.addWidget(settings_group)

        # Hum removal
        hum_group = QGroupBox("Hum Removal")
        hum_layout = QHBoxLayout(hum_group)
        self.hum_check = QCheckBox("Remove electrical hum")
        hum_layout.addWidget(self.hum_check)
        self.hum_combo = QComboBox()
        self.hum_combo.addItems(["60 Hz (US)", "50 Hz (EU/other)"])
        hum_layout.addWidget(self.hum_combo)
        layout.addWidget(hum_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)

        self.btn_apply = QPushButton("Apply Noise Reduction")
        self.btn_apply.setEnabled(has_profile)
        self.btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

        self.setStyleSheet(DIALOG_STYLE)

    def _on_capture(self):
        self.capture_profile = True
        self.apply_reduction = False
        self.accept()

    def _on_apply(self):
        self.strength = self.strength_slider.value() / 10.0
        self.floor = self.floor_slider.value() / 100.0
        self.remove_hum = self.hum_check.isChecked()
        self.hum_freq = 60.0 if self.hum_combo.currentIndex() == 0 else 50.0
        self.capture_profile = False
        self.apply_reduction = True
        self.accept()
