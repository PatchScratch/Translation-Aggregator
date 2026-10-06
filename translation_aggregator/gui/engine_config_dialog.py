"""Per-engine settings dialogs, opened from the gear button in each pane.

Like the original TA, each translation box carries its own configure button
with the settings related to that engine, instead of one universal dialog.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
    QGroupBox, QRadioButton,
)

from ..config import AppConfig
from ..translators.wwwjdic import MIRRORS, DEFAULT_MIRROR


class DeepLEngineDialog(QDialog):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("DeepL Settings")
        self.cfg = cfg

        layout = QVBoxLayout(self)
        g = QGroupBox("DeepL")
        l = QVBoxLayout(g)
        self.rb_free = QRadioButton("Free (web scraping) — frequently rate-limited / broken")
        self.rb_api = QRadioButton("Official DeepL API (requires API key)")
        if getattr(cfg, "deepl_mode", "free") == "api":
            self.rb_api.setChecked(True)
        else:
            self.rb_free.setChecked(True)
        l.addWidget(self.rb_free)
        l.addWidget(self.rb_api)
        self.key = QLineEdit(cfg.deepl_api_key)
        self.key.setPlaceholderText("DeepL API key")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        l.addWidget(QLabel("DeepL API key (API mode)"))
        l.addWidget(self.key)
        self.api_url = QLineEdit(getattr(cfg, "deepl_api_base_url", ""))
        self.api_url.setPlaceholderText("Optional API URL override")
        l.addWidget(QLabel("DeepL API base URL (optional)"))
        l.addWidget(self.api_url)
        layout.addWidget(g)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def accept(self):
        self.cfg.deepl_mode = "api" if self.rb_api.isChecked() else "free"
        self.cfg.deepl_api_key = self.key.text().strip()
        self.cfg.deepl_api_base_url = self.api_url.text().strip()
        super().accept()


class WwwjdicEngineDialog(QDialog):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("WWWJDIC Settings")
        self.cfg = cfg

        layout = QVBoxLayout(self)
        g = QGroupBox("WWWJDIC")
        l = QVBoxLayout(g)
        self.mirror = QLineEdit(getattr(cfg, "wwwjdic_mirror", DEFAULT_MIRROR))
        self.mirror.setPlaceholderText(DEFAULT_MIRROR)
        l.addWidget(QLabel("Mirror URL (known: " + ", ".join(MIRRORS[:2]) + ", …)"))
        l.addWidget(self.mirror)
        layout.addWidget(g)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def accept(self):
        self.cfg.wwwjdic_mirror = self.mirror.text().strip() or DEFAULT_MIRROR
        super().accept()


class OpenAIEngineDialog(QDialog):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("OpenAI-compatible API Settings")
        self.cfg = cfg

        layout = QVBoxLayout(self)
        g = QGroupBox("OpenAI-compatible API")
        l = QVBoxLayout(g)
        self.base = QLineEdit(getattr(cfg, "openai_base_url", "https://api.openai.com/v1"))
        self.base.setPlaceholderText("https://api.openai.com/v1 or http://127.0.0.1:1234/v1")
        self.key = QLineEdit(getattr(cfg, "openai_api_key", ""))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("API key (optional for local LM Studio)")
        self.model = QLineEdit(getattr(cfg, "openai_model", "gpt-4o-mini"))
        self.prompt = QLineEdit(getattr(cfg, "openai_system_prompt", ""))
        l.addWidget(QLabel("Base URL"))
        l.addWidget(self.base)
        l.addWidget(QLabel("API key"))
        l.addWidget(self.key)
        l.addWidget(QLabel("Model"))
        l.addWidget(self.model)
        l.addWidget(QLabel("System prompt ({src} / {dst} allowed)"))
        l.addWidget(self.prompt)
        layout.addWidget(g)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def accept(self):
        self.cfg.openai_base_url = self.base.text().strip() or "https://api.openai.com/v1"
        self.cfg.openai_api_key = self.key.text().strip()
        self.cfg.openai_model = self.model.text().strip() or "gpt-4o-mini"
        if self.prompt.text().strip():
            self.cfg.openai_system_prompt = self.prompt.text().strip()
        super().accept()


# Which engines have a settings dialog for their pane's gear button.
# Engines without related settings (google, bing, yandex, baidu, ...) get no
# gear; add a class here when they grow options.
ENGINE_CONFIG_DIALOGS = {
    "deepl": DeepLEngineDialog,
    "wwwjdic": WwwjdicEngineDialog,
    "openai": OpenAIEngineDialog,
}
