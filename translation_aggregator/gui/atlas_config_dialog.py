from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QDialogButtonBox, QLabel, QComboBox, QLineEdit, QPushButton
)

from ..config import AppConfig


# These match the range in the original AtlasDialogProc
# We map them to bit positions starting at 0 for IDC_ELLIPSES.
ATLAS_FLAG_NAMES = [
    ("Ellipses", "Ellipses"),
    ("Full width periods", "FullWidthPeriods"),
    ("Full width commas", "FullWidthCommas"),
    ("Full width question marks", "FullWidthQuestion"),
    ("Full width exclamation", "FullWidthExclamation"),
    ("Half to full width", "HalfToFull"),
    ("Remove line breaks", "RemoveLineBreaks"),
    ("Single line breaks", "SingleLineBreaks"),
]


class AtlasConfigDialog(QDialog):
    """ATLAS Configuration dialog, 100% port of the behavior in AtlasWindow.cpp + AtlasDialogProc."""

    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("ATLAS Configuration")
        self.cfg = cfg
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # Flags
        g_flags = QGroupBox("Output formatting")
        l_flags = QVBoxLayout(g_flags)

        self.checks: list[QCheckBox] = []
        current_flags = int(getattr(self.cfg, "atlas_flags", 0) or 0)

        for idx, (label, _) in enumerate(ATLAS_FLAG_NAMES):
            cb = QCheckBox(label)
            if current_flags & (1 << idx):
                cb.setChecked(True)
            l_flags.addWidget(cb)
            self.checks.append(cb)

        layout.addWidget(g_flags)

        # Rule Set
        g_rs = QGroupBox("Rule Set")
        l_rs = QVBoxLayout(g_rs)

        self.rs_combo = QComboBox()
        self.rs_combo.addItem(" None")
        # Try to find .trs files near the app or in a "Rule Sets" folder
        rs_dir = Path("Rule Sets")
        if not rs_dir.exists():
            # also check one level up (sometimes layout differs)
            rs_dir = Path("..") / "Rule Sets"
        if rs_dir.exists():
            for f in sorted(rs_dir.glob("*.trs")):
                self.rs_combo.addItem(f.name)
        else:
            # Allow manual entry
            self.rs_combo.setEditable(True)

        current_trs = getattr(self.cfg, "atlas_trs_path", "") or ""
        if current_trs:
            idx = self.rs_combo.findText(current_trs)
            if idx >= 0:
                self.rs_combo.setCurrentIndex(idx)
            else:
                self.rs_combo.addItem(current_trs)
                self.rs_combo.setCurrentText(current_trs)

        l_rs.addWidget(self.rs_combo)
        layout.addWidget(g_rs)

        # Environment
        g_env = QGroupBox("Environment")
        l_env = QVBoxLayout(g_env)

        self.env_combo = QComboBox()
        self.env_combo.setEditable(True)
        self.env_combo.addItem("General")

        # Try to discover environments from typical transenv.ini location
        # (same logic as the C++ code that reads %APPDATA%\Fujitsu\ATLAS\V14.0\transenv.ini)
        try:
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
            for ver in (14, 13):
                ini = Path(appdata) / "Fujitsu" / "ATLAS" / f"V{ver}.0" / "transenv.ini"
                if ini.exists():
                    try:
                        text = ini.read_text(encoding="shift_jis", errors="replace")
                    except Exception:
                        text = ini.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        line = line.strip()
                        if line.startswith("[") and line.endswith("]"):
                            env = line[1:-1].strip()
                            if env and self.env_combo.findText(env) < 0:
                                self.env_combo.addItem(env)
        except Exception:
            pass

        current_env = getattr(self.cfg, "atlas_environment", "General") or "General"
        idx = self.env_combo.findText(current_env)
        if idx >= 0:
            self.env_combo.setCurrentIndex(idx)
        else:
            self.env_combo.addItem(current_env)
            self.env_combo.setCurrentText(current_env)

        l_env.addWidget(self.env_combo)
        layout.addWidget(g_env)

        # Buttons
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        apply_btn = bb.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self._apply)
        layout.addWidget(bb)

    def _collect(self):
        flags = 0
        for idx, cb in enumerate(self.checks):
            if cb.isChecked():
                flags |= (1 << idx)

        trs = self.rs_combo.currentText().strip()
        if trs.lower() == "none" or trs == " None":
            trs = ""

        env = self.env_combo.currentText().strip() or "General"

        self.cfg.atlas_flags = flags
        self.cfg.atlas_trs_path = trs
        self.cfg.atlas_environment = env

    def _apply(self):
        self._collect()
        self.cfg.save()
        # live refresh if possible
        parent = self.parent()
        if parent and hasattr(parent, "_refresh_atlas_from_source"):
            try:
                parent._refresh_atlas_from_source()
            except Exception:
                pass

    def accept(self):
        self._collect()
        self.cfg.save()
        super().accept()
