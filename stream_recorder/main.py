"""Stream Recorder - record a live church stream on a schedule."""

import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Stream Recorder")
    app.setOrganizationName("AudioProcessor")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
