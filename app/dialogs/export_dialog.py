"""MP3 export dialog — quality picker."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
)


class ExportDialog(QDialog):
    """Let the user choose MP3 export quality."""

    BITRATES = [
        ("128 kbps (good — smaller files)", "128k"),
        ("192 kbps (high quality)", "192k"),
        ("256 kbps (very high quality)", "256k"),
        ("320 kbps (maximum quality)", "320k"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export MP3")
        self.setFixedSize(340, 130)
        self.bitrate = "192k"

        layout = QVBoxLayout(self)

        label = QLabel("Select MP3 quality:")
        layout.addWidget(label)

        self.combo = QComboBox()
        for label_text, _ in self.BITRATES:
            self.combo.addItem(label_text)
        self.combo.setCurrentIndex(1)  # default 192k
        layout.addWidget(self.combo)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Export")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

        self.setStyleSheet("""
            QDialog { background: #2b2b2b; color: #d0d0d0; }
            QComboBox { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; padding: 4px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #3a3a3a; color: #d0d0d0; selection-background-color: #4a4a4a; }
            QPushButton { background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; border-radius: 3px; padding: 4px 16px; }
            QPushButton:hover { background: #4a4a4a; }
        """)

    def _accept(self):
        idx = self.combo.currentIndex()
        self.bitrate = self.BITRATES[idx][1]
        self.accept()
