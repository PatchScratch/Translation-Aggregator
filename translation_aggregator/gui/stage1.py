"""Stage 1 GUI overlay: web engines + WWWJDIC + OpenAI. No ATLAS."""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QPushButton

from ..engines import TRANSLATOR_MAP, make_translator, DISPLAY_NAMES
from .config_dialog import ConfigDialog
from .window import MainWindow, TranslatorPane


class Stage1Window(MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translation Aggregator")
        self._engine_keys: list[str] = []
        self._add_settings_button()
        self._hide_atlas()
        self._load_web_engines()

    def _add_settings_button(self):
        btn = QPushButton("Settings")
        btn.setFixedWidth(90)
        btn.clicked.connect(self._open_settings)
        layout = self.btn_translate.parentWidget().layout() if self.btn_translate.parentWidget() else None
        if layout is None:
            layout = self.layout()
        layout.addWidget(btn)
        self.btn_settings = btn

    def _open_settings(self):
        dlg = ConfigDialog(self, self.config)
        if not dlg.exec():
            return
        self.config.save()
        keep = {getattr(self, "jpane", None), getattr(self, "mpane", None)}
        keep.discard(None)
        for pane in list(self.grid_order):
            if pane in keep:
                continue
            if pane in self.grid_order:
                self.grid_order.remove(pane)
            if pane in self.pane_list:
                self.pane_list.remove(pane)
            pane.hide()
            pane.setParent(None)
        self.panes = {}
        self.translators = []
        self._load_web_engines()

    def _hide_atlas(self):
        pane = getattr(self, "apane", None)
        if pane is None:
            return
        if pane in self.grid_order:
            self.grid_order.remove(pane)
        if pane in self.pane_list:
            self.pane_list.remove(pane)
        pane.hide()
        pane.setParent(None)
        self._refresh_grid_layout()

    def _load_web_engines(self):
        names = list(getattr(self.config, "enabled_translators", None) or [])
        if not names:
            names = ["bing", "wwwjdic"]
        self._engine_keys = []
        self.translators = []
        for key in names:
            if key not in TRANSLATOR_MAP:
                continue
            # Do not construct Playwright/DeepL/etc at startup — that hangs the UI.
            self._engine_keys.append(key)
            title = DISPLAY_NAMES.get(key, key)
            pane = TranslatorPane(title)
            pane._engine_key = key
            pane._engine = None
            self.panes[title] = pane
            self._register_pane(pane)
        self._refresh_grid_layout()

    def _engine_for_pane(self, pane):
        eng = getattr(pane, "_engine", None)
        if eng is not None:
            return eng
        key = getattr(pane, "_engine_key", None)
        if not key:
            return None
        try:
            eng = make_translator(key, self.config)
        except Exception as e:
            pane.edit.setPlainText(str(e))
            return None
        pane._engine = eng
        return eng

    def _on_translate_clicked(self):
        self._refresh_jparser_from_source()
        self._refresh_mecab_from_source()
        text = ""
        try:
            text = self.src_edit.toPlainText().strip()
        except Exception:
            return
        if not text:
            return
        self.btn_translate.setEnabled(False)
        QApplication.processEvents()
        try:
            for pane in list(self.grid_order):
                if not getattr(pane, "edit", None) or not getattr(pane, "_engine_key", None):
                    continue
                pane.edit.setPlainText("..." )
                QApplication.processEvents()
                eng = self._engine_for_pane(pane)
                if eng is None:
                    continue
                try:
                    res = eng.translate(text, src=self.src_lang, dst=self.dst_lang)
                    pane.edit.setPlainText((res.error or res.text or "").strip())
                except Exception as e:
                    pane.edit.setPlainText(str(e))
                QApplication.processEvents()
        finally:
            self.btn_translate.setEnabled(True)

    def _refresh_atlas_from_source(self):
        return
