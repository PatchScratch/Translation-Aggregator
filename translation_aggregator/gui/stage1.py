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
        self._add_settings_button()
        self._hide_atlas()
        self._load_web_engines()

    def _add_settings_button(self):
        btn = QPushButton("Settings")
        btn.setFixedWidth(90)
        btn.clicked.connect(self._open_settings)
        parent = self.btn_translate.parentWidget()
        layout = parent.layout() if parent is not None else self.layout()
        if layout is not None:
            layout.addWidget(btn)
        self.btn_settings = btn

    def _open_settings(self):
        dlg = ConfigDialog(self, self.config)
        if dlg.exec():
            self.config.save()
            self.translators = []
            # Drop old web panes; keep JParser / MeCab.
            keep = {getattr(self, "jpane", None), getattr(self, "mpane", None)}
            keep.discard(None)
            old = list(self.grid_order)
            for pane in old:
                if pane in keep:
                    continue
                if pane in self.grid_order:
                    self.grid_order.remove(pane)
                if pane in self.pane_list:
                    self.pane_list.remove(pane)
                pane.hide()
                pane.setParent(None)
            self.panes = {}
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
            names = ["google", "bing", "deepl", "yandex", "wwwjdic"]
        for key in names:
            if key not in TRANSLATOR_MAP:
                continue
            try:
                eng = make_translator(key, self.config)
            except Exception:
                continue
            if eng not in self.translators:
                self.translators.append(eng)
            title = DISPLAY_NAMES.get(key, eng.name)
            pane = self.panes.get(title) or self.panes.get(eng.name)
            if pane is None:
                pane = TranslatorPane(title)
                self.panes[title] = pane
                self.panes[eng.name] = pane
                self._register_pane(pane)
            pane._engine = eng
        self._refresh_grid_layout()

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
        for eng in self.translators:
            pane = self.panes.get(getattr(eng, "name", ""))
            if pane is None:
                pane = next(
                    (p for p in self.panes.values() if getattr(p, "_engine", None) is eng),
                    None,
                )
            if pane is None or not getattr(pane, "edit", None):
                continue
            pane.edit.setPlainText("..." )
            QApplication.processEvents()
            try:
                res = eng.translate(text, src=self.src_lang, dst=self.dst_lang)
                pane.edit.setPlainText((res.error or res.text or "").strip())
            except Exception as e:
                pane.edit.setPlainText(str(e))

    def _refresh_atlas_from_source(self):
        return
