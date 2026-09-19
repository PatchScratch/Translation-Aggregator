from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QLabel, QLineEdit,
    QDialogButtonBox, QGroupBox, QRadioButton,
)

from ..config import AppConfig
from ..engines import DISPLAY_NAMES, TRANSLATOR_MAP
from ..translators.wwwjdic import MIRRORS, DEFAULT_MIRROR


class ConfigDialog(QDialog):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.cfg = cfg
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

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

        g3 = QGroupBox("Translators")
        l3 = QVBoxLayout(g3)
        self.trans_checks = {}
        for name in TRANSLATOR_MAP:
            cb = QCheckBox(DISPLAY_NAMES.get(name, name))
            cb.setChecked(name in self.cfg.enabled_translators)
            self.trans_checks[name] = cb
            l3.addWidget(cb)
        layout.addWidget(g3)

        g5 = QGroupBox("DeepL")
        l5 = QVBoxLayout(g5)
        self.rb_deepl_free = QRadioButton("Free (web scraping) — frequently rate-limited / broken")
        self.rb_deepl_api = QRadioButton("Official DeepL API (requires API key)")
        if getattr(self.cfg, "deepl_mode", "free") == "api":
            self.rb_deepl_api.setChecked(True)
        else:
            self.rb_deepl_free.setChecked(True)
        l5.addWidget(self.rb_deepl_free)
        l5.addWidget(self.rb_deepl_api)
        self.deepl_key = QLineEdit(self.cfg.deepl_api_key)
        self.deepl_key.setPlaceholderText("DeepL API key")
        self.deepl_key.setEchoMode(QLineEdit.EchoMode.Password)
        l5.addWidget(QLabel("DeepL API key (API mode)"))
        l5.addWidget(self.deepl_key)
        self.deepl_api_url = QLineEdit(getattr(self.cfg, "deepl_api_base_url", ""))
        self.deepl_api_url.setPlaceholderText("Optional API URL override")
        l5.addWidget(QLabel("DeepL API base URL (optional)"))
        l5.addWidget(self.deepl_api_url)
        layout.addWidget(g5)

        g6 = QGroupBox("WWWJDIC")
        l6 = QVBoxLayout(g6)
        self.wwwjdic_mirror = QLineEdit(getattr(self.cfg, "wwwjdic_mirror", DEFAULT_MIRROR))
        self.wwwjdic_mirror.setPlaceholderText(DEFAULT_MIRROR)
        l6.addWidget(QLabel("Mirror URL (known: " + ", ".join(MIRRORS[:2]) + ", …)"))
        l6.addWidget(self.wwwjdic_mirror)
        layout.addWidget(g6)

        g7 = QGroupBox("OpenAI-compatible API")
        l7 = QVBoxLayout(g7)
        self.openai_base = QLineEdit(getattr(self.cfg, "openai_base_url", "https://api.openai.com/v1"))
        self.openai_base.setPlaceholderText("https://api.openai.com/v1 or http://127.0.0.1:1234/v1")
        self.openai_key = QLineEdit(getattr(self.cfg, "openai_api_key", ""))
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setPlaceholderText("API key (optional for local LM Studio)")
        self.openai_model = QLineEdit(getattr(self.cfg, "openai_model", "gpt-4o-mini"))
        self.openai_prompt = QLineEdit(getattr(self.cfg, "openai_system_prompt", ""))
        l7.addWidget(QLabel("Base URL"))
        l7.addWidget(self.openai_base)
        l7.addWidget(QLabel("API key"))
        l7.addWidget(self.openai_key)
        l7.addWidget(QLabel("Model"))
        l7.addWidget(self.openai_model)
        l7.addWidget(QLabel("System prompt ({src} / {dst} allowed)"))
        l7.addWidget(self.openai_prompt)
        layout.addWidget(g7)

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
        self.cfg.auto_clipboard = self.cb_clip.isChecked()
        self.cfg.enable_substitutions = self.cb_sub.isChecked()
        self.cfg.auto_hiragana = self.cb_hira.isChecked()
        enabled = [n for n, cb in self.trans_checks.items() if cb.isChecked()]
        self.cfg.enabled_translators = enabled or ["google"]
        self.cfg.deepl_mode = "api" if self.rb_deepl_api.isChecked() else "free"
        self.cfg.deepl_api_key = self.deepl_key.text().strip()
        self.cfg.deepl_api_base_url = self.deepl_api_url.text().strip()
        self.cfg.wwwjdic_mirror = self.wwwjdic_mirror.text().strip() or DEFAULT_MIRROR
        self.cfg.openai_base_url = self.openai_base.text().strip() or "https://api.openai.com/v1"
        self.cfg.openai_api_key = self.openai_key.text().strip()
        self.cfg.openai_model = self.openai_model.text().strip() or "gpt-4o-mini"
        if self.openai_prompt.text().strip():
            self.cfg.openai_system_prompt = self.openai_prompt.text().strip()
        self.cfg.dictionaries_dir = self.dict_dir.text().strip() or "dictionaries"
        self.cfg.mecab_path = self.mecab_path.text().strip()
        super().accept()
