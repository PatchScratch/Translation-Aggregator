"""GUI entry point (`transagg-gui`): QApplication, color scheme, tooltip palette, Stage1Window."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QIcon

from .stage1 import Stage1Window
from ..config import config
from ..extras import ensure_on_sys_path
from . import theme


def _icon_path() -> str:
    """App icon for the window title bar / taskbar (bundled per build type)."""
    name = "icon.ico" if sys.platform == "win32" else "icon.png"
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(getattr(sys, "_MEIPASS", "")) / "assets" / name)
    elif os.environ.get("APPDIR"):
        # python-appimage puts the recipe icon at the AppDir root
        candidates.append(Path(os.environ["APPDIR"]) / "TranslationAggregator.png")
        candidates.append(Path(os.environ["APPDIR"]) / "assets" / "icon.png")
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / name)
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "icon.png")
    for c in candidates:
        try:
            if c and c.is_file():
                return str(c)
        except OSError:
            continue
    return ""


def main():
    # Optional components (MeCab binding + dictionary) pip-installed by the
    # in-app installer live in the extras dir; portable builds find them here.
    ensure_on_sys_path()

    # NOTE: do not set an explicit AppUserModelID here. With one, the taskbar
    # looks for an installed shortcut carrying that ID and shows a generic
    # icon when none exists; deriving it from the exe path works correctly.

    app = QApplication(sys.argv)

    icon = _icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))

    theme.apply_theme(getattr(config, "gui_color_scheme", "system"))

    pal = app.palette()
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("black"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffe1"))
    app.setPalette(pal)

    current_ss = app.styleSheet() or ""
    if "QToolTip" not in current_ss:
        app.setStyleSheet(current_ss + "\nQToolTip { color: black; }")

    win = Stage1Window()
    # instance-level icon in addition to the app-level one above: Windows
    # re-creates the native window when window flags change (topmost toggle),
    # and the taskbar reliably keeps the icon only when it is on the window
    if icon:
        win.setWindowIcon(QIcon(icon))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
