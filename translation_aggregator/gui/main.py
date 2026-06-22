from __future__ import annotations

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
import sys

from .window import MainWindow


def main():
    app = QApplication(sys.argv)

    # Force glossary bubble (QToolTip) text to black for JParser and MeCab panes.
    # Apply on the current palette (in case a dark theme was loaded).
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("black"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffe1"))
    app.setPalette(pal)

    # Append to any existing app stylesheet so QToolTip text is forced black.
    current_ss = app.styleSheet() or ""
    if "QToolTip" not in current_ss:
        app.setStyleSheet(current_ss + "\nQToolTip { color: black; }")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
