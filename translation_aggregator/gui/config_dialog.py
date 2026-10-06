from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QLabel, QLineEdit,
    QDialogButtonBox, QGroupBox, QComboBox,
)

from ..config import AppConfig
from ..engines import DISPLAY_NAMES, TRANSLATOR_MAP
from .theme import SCHEMES, SCHEME_LABELS


class ConfigDialog(QDialog):
    """App-wide settings: which panes exist and general options.

    Engine-specific settings live in each pane's gear dialog
    (engine_config_dialog.py), like the original TA.
    """

    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.cfg = cfg
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        g1 = QGroupBox("General")
        l1 = QVBoxLayout(g1)
        self.cb_sub = QCheckBox("Enable substitutions")
        self.cb_sub.setChecked(self.cfg.enable_substitutions)
        self.cb_hira = QCheckBox("Auto convert romaji to hiragana when source is Japanese")
        self.cb_hira.setChecked(self.cfg.auto_hiragana)
        scheme_row = QVBoxLayout()
        scheme_row.addWidget(QLabel("Color scheme"))
        self.combo_scheme = QComboBox()
        for s in SCHEMES:
            self.combo_scheme.addItem(SCHEME_LABELS[s], s)
        current = getattr(self.cfg, "gui_color_scheme", "system")
        if current not in SCHEMES:
            current = "system"
        self.combo_scheme.setCurrentIndex(SCHEMES.index(current))
        scheme_row.addWidget(self.combo_scheme)
        l1.addWidget(self.cb_sub)
        l1.addWidget(self.cb_hira)
        l1.addLayout(scheme_row)
        layout.addWidget(g1)

        g3 = QGroupBox("Translators")
        l3 = QVBoxLayout(g3)
        self.trans_checks = {}
        for name in TRANSLATOR_MAP:
            cb = QCheckBox(DISPLAY_NAMES.get(name, name))
            cb.setChecked(name in self.cfg.enabled_translators)
            self.trans_checks[name] = cb
            l3.addWidget(cb)
        layout.addWidget(g3)

        g4 = QGroupBox("Paths")
        l4 = QVBoxLayout(g4)
        self.dict_dir = QLineEdit(self.cfg.dictionaries_dir)
        self.mecab_path = QLineEdit(self.cfg.mecab_path)
        l4.addWidget(QLabel("Dictionaries directory"))
        l4.addWidget(self.dict_dir)
        l4.addWidget(QLabel("MeCab path (optional)"))
        l4.addWidget(self.mecab_path)
        layout.addWidget(g4)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def accept(self):
        self.cfg.enable_substitutions = self.cb_sub.isChecked()
        self.cfg.auto_hiragana = self.cb_hira.isChecked()
        self.cfg.gui_color_scheme = self.combo_scheme.currentData() or "system"
        enabled = [n for n, cb in self.trans_checks.items() if cb.isChecked()]
        self.cfg.enabled_translators = enabled or ["google"]
        self.cfg.dictionaries_dir = self.dict_dir.text().strip() or "dictionaries"
        self.cfg.mecab_path = self.mecab_path.text().strip()
        super().accept()
