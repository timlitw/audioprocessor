"""Export options dialog — choose what to include in an exported transcript."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox

from core.settings import get_export_options, set_export_options


class ExportOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Transcript")
        opts = get_export_options()

        layout = QVBoxLayout(self)
        self.timestamps_cb = QCheckBox("Include timestamps")
        self.timestamps_cb.setChecked(opts["timestamps"])
        self.speakers_cb = QCheckBox("Include speaker names")
        self.speakers_cb.setChecked(opts["speakers"])
        self.types_cb = QCheckBox("Include type (Singing)")
        self.types_cb.setChecked(opts["types"])
        layout.addWidget(self.timestamps_cb)
        layout.addWidget(self.speakers_cb)
        layout.addWidget(self.types_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> dict:
        return {
            "timestamps": self.timestamps_cb.isChecked(),
            "speakers": self.speakers_cb.isChecked(),
            "types": self.types_cb.isChecked(),
        }

    def accept(self):
        set_export_options(self.options())
        super().accept()
