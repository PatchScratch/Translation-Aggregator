"""In-app installer for the MeCab pane (fugashi binding + unidic-lite dictionary).

Works in every build, portable ones included. The binding is a wheel, so pip
installs it with `--target` into the per-user extras directory (see
translation_aggregator.extras). The dictionary ships only as an sdist, which
pip cannot build inside the frozen exe — its dicdir is pre-built data, so it
is downloaded from PyPI and unpacked directly (about 50 MB download, ~300 MB
stored once per user, outside the app, so it survives app updates).
"""

from __future__ import annotations

import subprocess
import sys
import time

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout,
)

from .. import extras
from ..mecab import MecabWrapper, MecabError


def mecab_status() -> tuple[bool, str]:
    """(available, human detail) for the current process."""
    try:
        MecabWrapper()
        return True, "MeCab is already working; nothing to do."
    except MecabError as e:
        return False, str(e)


class _InstallThread(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(bool, str)  # ok, summary

    def _install_args(self) -> list[str]:
        return [
            "install",
            "--target", str(extras.extras_dir()),
            # only wheels: a source build would fail for users without compilers
            "--only-binary", ":all:",
            # refresh an existing install (pip warns and skips otherwise)
            "--upgrade",
            "--quiet",
            "fugashi",
        ]

    def _run_subprocess(self, args: list[str]) -> tuple[bool, str]:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", *args],
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
        extras.extras_dir().mkdir(parents=True, exist_ok=True)
        args = self._install_args()
        started = time.time()

        self.line.emit("Installing the fugashi MeCab binding…")
        if extras.is_frozen_exe():
            # No interpreter to spawn; pip runs inside this process (blocking
            # this worker thread, not the UI). pip prints no streamable lines.
            ok, last = extras.pip_install(args)
            if not ok:
                self.done.emit(False, f"pip install failed: {last}")
                return
        else:
            ok, last = self._run_subprocess(args)
            if not ok:
                self.done.emit(False, f"pip install failed: {last}")
                return

        ok, summary = extras.install_mecab_dict(self.line.emit)
        if not ok:
            self.done.emit(False, summary)
            return

        extras.ensure_on_sys_path()
        # drop any cached import failure so the new install is picked up
        for mod in ("fugashi", "unidic_lite", "ipadic", "MeCab"):
            sys.modules.pop(mod, None)
        ok, detail = mecab_status()
        if ok:
            self.done.emit(True, f"MeCab is ready (took {time.time() - started:.0f}s); the MeCab pane will use it on the next translation.")
        else:
            # e.g. a future pip that blocks same-process imports after an
            # install: the install itself is on disk, a restart picks it up
            self.done.emit(True, "Installed. This app session could not load it "
                                 f"({detail}); restart the app and the MeCab pane will work.")


class InstallMecabDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install MeCab (MeCab pane)")
        self.resize(640, 420)
        self._thread = None

        layout = QVBoxLayout(self)
        available, detail = mecab_status()

        if available:
            layout.addWidget(QLabel(
                "MeCab is already installed and working — the MeCab pane can "
                "use it. Nothing to do.\n\n" + detail
            ))
            close = QPushButton("Close")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        layout.addWidget(QLabel(
            "This installs the MeCab tokenizer for the MeCab pane:\n"
            "  - fugashi (the MeCab python binding)\n"
            "  - unidic-lite (its dictionary — about 50 MB downloaded, ~300 MB\n"
            "    stored once per user, outside the app, so it survives updates)\n\n"
            "The download can take a few minutes. Everything else in the app "
            "works without it."
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
        self._thread = _InstallThread(self)
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
