from __future__ import annotations

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
import sys

from .stage1 import Stage1Window


def main():
    app = QApplication(sys.argv)

    pal = app.palette()
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("black"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffe1"))
    app.setPalette(pal)

    current_ss = app.styleSheet() or ""
    if "QToolTip" not in current_ss:
        app.setStyleSheet(current_ss + "\nQToolTip { color: black; }")

    win = Stage1Window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
