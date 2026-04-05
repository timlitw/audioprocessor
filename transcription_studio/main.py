"""Transcription Studio — Transcribe audio, identify speakers, generate video."""

import sys
from PyQt6.QtWidgets import QApplication
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Transcription Studio")
    app.setOrganizationName("AudioProcessor")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
