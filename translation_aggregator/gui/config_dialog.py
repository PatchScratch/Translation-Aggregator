from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QGroupBox, QComboBox, QTextEdit, QRadioButton
)

from ..config import AppConfig


class ConfigDialog(QDialog):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.cfg = cfg
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # General
        g1 = QGroupBox("General")
        l1 = QVBoxLayout(g1)
        self.cb_clip = QCheckBox("Auto clipboard monitoring")
        self.cb_clip.setChecked(self.cfg.auto_clipboard)
        self.cb_sub = QCheckBox("Enable substitutions")
        self.cb_sub.setChecked(self.cfg.enable_substitutions)
        self.cb_hira = QCheckBox("Auto convert romaji to hiragana when source is Japanese")
        self.cb_hira.setChecked(self.cfg.auto_hiragana)
        l1.addWidget(self.cb_clip)
        l1.addWidget(self.cb_sub)
        l1.addWidget(self.cb_hira)
        layout.addWidget(g1)

        # Translators
        g3 = QGroupBox("Translators")
        l3 = QVBoxLayout(g3)
        self.trans_checks = {}
        for name in ["google", "bing", "deepl", "baidu", "baidu_pw", "yandex"]:
            cb = QCheckBox(name.capitalize())
            cb.setChecked(name in self.cfg.enabled_translators)
            self.trans_checks[name] = cb
            l3.addWidget(cb)
        layout.addWidget(g3)

        # DeepL mode
        g5 = QGroupBox("DeepL")
        l5 = QVBoxLayout(g5)

        self.rb_deepl_free = QRadioButton("Free (web scraping) — frequently rate-limited / broken")
        self.rb_deepl_api = QRadioButton("Official DeepL API (recommended, requires API key)")
        if getattr(self.cfg, "deepl_mode", "free") == "api":
            self.rb_deepl_api.setChecked(True)
        else:
            self.rb_deepl_free.setChecked(True)

        l5.addWidget(self.rb_deepl_free)
        l5.addWidget(self.rb_deepl_api)

        self.deepl_key = QLineEdit(self.cfg.deepl_api_key)
        self.deepl_key.setPlaceholderText("DeepL API key (e.g. 01234567-89ab-cdef-0123-456789abcdef:fx)")
        self.deepl_key.setEchoMode(QLineEdit.EchoMode.Password)
        l5.addWidget(QLabel("DeepL API Key (only used in API mode)"))
        l5.addWidget(self.deepl_key)

        self.deepl_api_url = QLineEdit(getattr(self.cfg, "deepl_api_base_url", ""))
        self.deepl_api_url.setPlaceholderText("Optional: override API URL (e.g. https://api-free.deepl.com/v2/translate)")
        l5.addWidget(QLabel("DeepL API Base URL (advanced, optional)"))
        l5.addWidget(self.deepl_api_url)

        note = QLabel("Note: Free mode uses the same unofficial scraping method as the original TA and is frequently rate-limited (429).")
        note.setStyleSheet("color: #888;")
        l5.addWidget(note)

        layout.addWidget(g5)

        # Paths
        g4 = QGroupBox("Paths")
        l4 = QVBoxLayout(g4)
        self.dict_dir = QLineEdit(self.cfg.dictionaries_dir)
        self.mecab_path = QLineEdit(self.cfg.mecab_path)
        l4.addWidget(QLabel("Dictionaries directory"))
        l4.addWidget(self.dict_dir)
        l4.addWidget(QLabel("MeCab path (optional)"))
        l4.addWidget(self.mecab_path)
        layout.addWidget(g4)

        # Buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def accept(self):
        self.cfg.auto_clipboard = self.cb_clip.isChecked()
        self.cfg.enable_substitutions = self.cb_sub.isChecked()
        self.cfg.auto_hiragana = self.cb_hira.isChecked()

        enabled = [n for n, cb in self.trans_checks.items() if cb.isChecked()]
        self.cfg.enabled_translators = enabled or ["google"]

        # DeepL mode
        self.cfg.deepl_mode = "api" if self.rb_deepl_api.isChecked() else "free"
        self.cfg.deepl_api_key = self.deepl_key.text().strip()
        self.cfg.deepl_api_base_url = self.deepl_api_url.text().strip()

        self.cfg.dictionaries_dir = self.dict_dir.text().strip() or "dictionaries"
        self.cfg.mecab_path = self.mecab_path.text().strip()

        super().accept()
