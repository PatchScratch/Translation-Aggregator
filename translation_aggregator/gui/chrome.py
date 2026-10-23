"""Window chrome for the frameless main window.

Replaces the native title bar + menu bar with one row, Novel Mill's design
language: app title on the left (drag to move), window buttons on the
right, and the whole application menu behind a hamburger button like a
browser. The menu itself is built by gui/menubar.py (build_app_menu).

On Windows the drag/move handling is native — MainWindow answers
WM_NCHITTEST for this row (HTCAPTION) — so snapping, double-click-maximize
and Aero Shake all work. The fallback here (startSystemMove) covers
non-Windows builds.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from . import theme


class WindowChrome(QWidget):
    def __init__(self, win, parent=None):
        super().__init__(parent)
        self._win = win
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(34)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 4, 2)
        lay.setSpacing(6)

        self.hamburger = QToolButton()
        self.hamburger.setText("\u2630")  # ☰
        self.hamburger.setToolTip("Menu (File / View / Tools / Help)")
        self.hamburger.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hamburger.clicked.connect(self._open_menu)
        lay.addWidget(self.hamburger)

        self.title = QLabel("Translation Aggregator")
        lay.addWidget(self.title, 1)

        self.btn_min = QToolButton()
        self.btn_min.setText("\u2013")  # –
        self.btn_min.setToolTip("Minimize")
        self.btn_min.clicked.connect(self._minimize)
        lay.addWidget(self.btn_min)

        self.btn_max = QToolButton()
        self.btn_max.setText("\u25a1")  # □
        self.btn_max.setToolTip("Maximize")
        self.btn_max.clicked.connect(self._toggle_maximize)
        lay.addWidget(self.btn_max)

        self.btn_close = QToolButton()
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setText("\u2715")  # ✕
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self._close)
        lay.addWidget(self.btn_close)

        self.apply_theme()

    # ---------- theme ----------

    def apply_theme(self):
        p = theme.palette()
        self.setStyleSheet(
            f"WindowChrome {{ background-color: {p['window']}; "
            f"border-bottom: 1px solid {p['border']}; }}"
            f"QLabel {{ background: transparent; color: {p['text']}; font-weight: 600; }}"
            f"QToolButton {{ background: transparent; color: {p['text']}; "
            f"border: none; font-size: 13px; padding: 3px 9px; }}"
            f"QToolButton:hover {{ background-color: {p['button_hover']}; }}"
            f"QToolButton#btn_close:hover {{ background-color: #c42b1c; "
            f"color: #ffffff; }}"
        )

    # ---------- window buttons ----------

    def _minimize(self):
        try:
            self._win.showMinimized()
        except Exception:
            pass

    def _toggle_maximize(self):
        try:
            if self._win.isMaximized():
                self._win.showNormal()
                self.btn_max.setText("\u25a1")  # □
                self.btn_max.setToolTip("Maximize")
            else:
                self._win.showMaximized()
                self.btn_max.setText("\u2750")  # ❐
                self.btn_max.setToolTip("Restore")
        except Exception:
            pass

    def _close(self):
        try:
            self._win.close()
        except Exception:
            pass

    def _open_menu(self):
        try:
            menu = getattr(self._win, "app_menu", None)
            if menu is None:
                return
            menu.exec(self.hamburger.mapToGlobal(self.hamburger.rect().bottomLeft()))
        except Exception:
            pass

    # ---------- dragging (non-Windows fallback) ----------

    def mousePressEvent(self, e: QMouseEvent):
        try:
            if e.button() == Qt.MouseButton.LeftButton and self._win.windowHandle():
                self._win.windowHandle().startSystemMove()
        except Exception:
            pass

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        try:
            if e.button() == Qt.MouseButton.LeftButton:
                self._toggle_maximize()
        except Exception:
            pass
