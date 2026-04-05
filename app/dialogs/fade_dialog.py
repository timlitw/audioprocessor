"""Fade in/out dialog — choose duration."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDoubleSpinBox,
)

DIALOG_STYLE = """
    QDialog { background: #2b2b2b; color: #d0d0d0; }
    QDoubleSpinBox { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; padding: 4px; }
    QPushButton { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; border-radius: 3px; padding: 4px 16px; }
    QPushButton:hover { background: #4a4a4a; }
"""


class FadeDialog(QDialog):
    def __init__(self, fade_type: str = "in", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Fade {fade_type.title()}")
        self.setFixedSize(280, 120)
        self.duration_seconds = 2.0

        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel(f"Fade {fade_type} duration (seconds):"))
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0.1, 30.0)
        self.spin.setValue(2.0)
        self.spin.setSingleStep(0.5)
        row.addWidget(self.spin)
        layout.addLayout(row)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)
        ok = QPushButton("Apply")
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        btn_layout.addWidget(ok)
        layout.addLayout(btn_layout)

        self.setStyleSheet(DIALOG_STYLE)

    def _accept(self):
        self.duration_seconds = self.spin.value()
        self.accept()
