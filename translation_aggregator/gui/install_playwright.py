"""In-app installer for the optional Playwright backend (Baidu engine).

Runs `pip install playwright` and `playwright install chromium` in a
worker thread, streaming the output into a dialog. Idempotent: with
everything already installed both steps finish in seconds. In a frozen
(PyInstaller) build there is no pip/Python to install into, so the
dialog explains that the Baidu engine needs the pip installation of
the app instead.
"""
from __future__ import annotations

import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout,
)

import os

from ..translators.baidu import playwright_status


def _readonly_install() -> bool:
    """True when the app cannot pip-install into itself (portable builds)."""
    return bool(getattr(sys, "frozen", False) or os.environ.get("APPIMAGE"))


class _InstallThread(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(bool, str)  # ok, summary

    def __init__(self, python_exe: str, parent=None):
        super().__init__(parent)
        self._python = python_exe

    def _run(self, args: list[str]) -> tuple[bool, str]:
        proc = subprocess.Popen(
            [self._python, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        last = ""
        assert proc.stdout is not None
        for raw in proc.stdout:
            text = raw.rstrip()
            if text:
                last = text
                self.line.emit(text)
        proc.wait()
        return proc.returncode == 0, last

    def run(self):
        ok, last = self._run(["-m", "pip", "install", "--quiet", "playwright"])
        if not ok:
            self.done.emit(False, f"pip install failed: {last}")
            return
        self.line.emit("")
        self.line.emit("Downloading the Chromium browser (about 150 MB, once per machine)…")
        ok, last = self._run(["-m", "playwright", "install", "chromium"])
        if not ok:
            self.done.emit(False, f"browser install failed: {last}")
            return
        self.done.emit(True, "Playwright and Chromium are ready; the Baidu pane will use them on the next translation.")


class InstallPlaywrightDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install Playwright (Baidu engine)")
        self.resize(640, 420)
        self._thread = None

        layout = QVBoxLayout(self)
        module_ok, chromium_ok = playwright_status()

        if _readonly_install():
            layout.addWidget(QLabel(
                "This is a portable build (single-file exe / AppImage), which "
                "bundles everything it can and cannot install Python packages "
                "into itself.\n\n"
                "The Baidu (Playwright) engine is only available in the "
                "pip installation of the app:\n\n"
                "    pip install -e \".[browser]\"\n"
                "    playwright install chromium"
            ))
            close = QPushButton("Close")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        if module_ok and chromium_ok:
            layout.addWidget(QLabel(
                "Playwright and its Chromium browser are already installed - "
                "the Baidu pane can use them. Nothing to do."
            ))
            close = QPushButton("Close")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        missing = []
        if not module_ok:
            missing.append("the playwright package")
        if not chromium_ok:
            missing.append("the Chromium browser (~150 MB, downloaded once)")
        layout.addWidget(QLabel(
            "This installs " + " and ".join(missing) +
            " for the Baidu (Playwright) translation engine.\n"
            "Everything else in the app works without it."
        ))

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log)

        buttons = QHBoxLayout()
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self._start)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(self.install_btn)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def _start(self):
        if self._thread is not None and self._thread.isRunning():
            return
        self.install_btn.setEnabled(False)
        self.log.clear()
        self._thread = _InstallThread(sys.executable, self)
        self._thread.line.connect(self.log.appendPlainText)
        self._thread.done.connect(self._finished)
        self._thread.start()

    def _finished(self, ok: bool, summary: str):
        self.log.appendPlainText("")
        self.log.appendPlainText(summary)
        self.install_btn.setEnabled(True)
        if ok:
            self.install_btn.setEnabled(False)

    def closeEvent(self, event):
        # daemon-like: let the install continue if the dialog is closed
        if self._thread is not None and self._thread.isRunning():
            self._thread.setParent(None)
        super().closeEvent(event)
