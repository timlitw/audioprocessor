"""Shared dark theme for the Transcription Studio."""

DARK_THEME = """
    QMainWindow, QWidget { background-color: #2b2b2b; color: #d0d0d0; }
    QMenuBar { background-color: #2b2b2b; color: #d0d0d0; }
    QMenuBar::item:selected { background-color: #3d3d3d; }
    QMenu { background-color: #2b2b2b; color: #d0d0d0; border: 1px solid #555; }
    QMenu::item:selected { background-color: #3d3d3d; }
    QMenu::item:disabled { color: #666; }
    QTabWidget::pane { border: 1px solid #444; background: #2b2b2b; }
    QTabBar::tab {
        background: #333; color: #aaa; padding: 8px 20px;
        border: 1px solid #444; border-bottom: none; margin-right: 2px;
    }
    QTabBar::tab:selected { background: #2b2b2b; color: #d0d0d0; border-bottom: 2px solid #00cc44; }
    QTabBar::tab:hover { background: #3d3d3d; }
    QScrollBar:vertical {
        background: #1e1e1e; width: 12px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #555; min-height: 30px; border-radius: 3px;
    }
    QScrollBar::handle:vertical:hover { background: #666; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal {
        background: #1e1e1e; height: 12px; margin: 0;
    }
    QScrollBar::handle:horizontal {
        background: #555; min-width: 30px; border-radius: 3px;
    }
    QScrollBar::handle:horizontal:hover { background: #666; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QPushButton {
        background: #3a3a3a; color: #d0d0d0; border: 1px solid #555;
        border-radius: 3px; padding: 5px 14px;
    }
    QPushButton:hover { background: #4a4a4a; }
    QPushButton:pressed { background: #2a2a2a; }
    QPushButton:disabled { color: #666; background: #333; }
    QComboBox {
        background: #3a3a3a; color: #d0d0d0; border: 1px solid #555; padding: 4px 8px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background: #3a3a3a; color: #d0d0d0; selection-background-color: #4a4a4a; }
    QLabel { color: #d0d0d0; }
    QGroupBox {
        border: 1px solid #555; border-radius: 4px; margin-top: 8px;
        padding-top: 14px; color: #d0d0d0;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; }
    QProgressBar {
        background: #1e1e1e; border: 1px solid #555; border-radius: 3px;
        text-align: center; color: #d0d0d0;
    }
    QProgressBar::chunk { background: #00cc44; border-radius: 2px; }
    QListWidget, QTableWidget {
        background: #1e1e1e; color: #d0d0d0; border: 1px solid #444;
        alternate-background-color: #252525;
    }
    QListWidget::item:selected, QTableWidget::item:selected {
        background: #3a5a8a;
    }
    QLineEdit, QTextEdit, QPlainTextEdit {
        background: #1e1e1e; color: #d0d0d0; border: 1px solid #555;
        padding: 4px; selection-background-color: #3a5a8a;
    }
    QStatusBar { background: #1e1e1e; color: #b0b0b0; }
    QToolBar { background: #2b2b2b; border-bottom: 1px solid #444; spacing: 2px; padding: 2px; }
    QSlider::groove:horizontal { background: #3a3a3a; height: 6px; border-radius: 3px; }
    QSlider::handle:horizontal { background: #00cc44; width: 14px; margin: -4px 0; border-radius: 7px; }
    QSplitter::handle { background: #444; }
"""
