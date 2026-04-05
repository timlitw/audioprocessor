"""Normalize dialog — peak or RMS normalization with target level."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QDoubleSpinBox, QRadioButton, QButtonGroup,
)

DIALOG_STYLE = """
    QDialog { background: #2b2b2b; color: #d0d0d0; }
    QComboBox, QDoubleSpinBox { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; padding: 4px; }
    QPushButton { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; border-radius: 3px; padding: 4px 16px; }
    QPushButton:hover { background: #4a4a4a; }
    QRadioButton { color: #d0d0d0; }
"""


class NormalizeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Normalize")
        self.setFixedSize(300, 200)
        self.mode = "peak"
        self.target_db = -1.0

        layout = QVBoxLayout(self)

        # Mode selection
        self.radio_peak = QRadioButton("Peak normalization")
        self.radio_peak.setChecked(True)
        self.radio_rms = QRadioButton("RMS normalization")

        group = QButtonGroup(self)
        group.addButton(self.radio_peak)
        group.addButton(self.radio_rms)

        layout.addWidget(self.radio_peak)
        layout.addWidget(self.radio_rms)

        # Target level
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target level (dB):"))
        self.spin_target = QDoubleSpinBox()
        self.spin_target.setRange(-30.0, 0.0)
        self.spin_target.setValue(-1.0)
        self.spin_target.setSingleStep(0.5)
        target_row.addWidget(self.spin_target)
        layout.addLayout(target_row)

        # Update default when mode changes
        self.radio_rms.toggled.connect(lambda checked: self.spin_target.setValue(-18.0) if checked else None)
        self.radio_peak.toggled.connect(lambda checked: self.spin_target.setValue(-1.0) if checked else None)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)
        ok = QPushButton("Normalize")
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        btn_layout.addWidget(ok)
        layout.addLayout(btn_layout)

        self.setStyleSheet(DIALOG_STYLE)

    def _accept(self):
        self.mode = "peak" if self.radio_peak.isChecked() else "rms"
        self.target_db = self.spin_target.value()
        self.accept()
