"""Stage 1 GUI overlay: web engines + WWWJDIC + OpenAI. No ATLAS."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QPushButton

from ..engines import TRANSLATOR_MAP, make_translator, DISPLAY_NAMES
from .config_dialog import ConfigDialog
from .window import MainWindow, TranslatorPane


class _EngineWorker(QObject):
    one_done = pyqtSignal(str, str)  # title, text
    finished = pyqtSignal()

    def __init__(self, jobs, src, dst, cfg):
        super().__init__()
        self.jobs = jobs  # list of (title, key)
        self.src = src
        self.dst = dst
        self.cfg = cfg
        self._stop = False

    def run(self):
        for title, key in self.jobs:
            if self._stop:
                break
            try:
                eng = make_translator(key, self.cfg)
                res = eng.translate(self.text, src=self.src, dst=self.dst)
                out = (res.error or res.text or "").strip()
            except Exception as e:
                out = str(e)
            self.one_done.emit(title, out)
        self.finished.emit()

    def set_text(self, text: str):
        self.text = text


class Stage1Window(MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translation Aggregator")
        self._engine_keys: list[str] = []
        self._thread = None
        self._worker = None
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
            self._engine_keys.append(key)
            title = DISPLAY_NAMES.get(key, key)
            pane = TranslatorPane(title)
            pane._engine_key = key
            pane._engine = None
            self.panes[title] = pane
            self._register_pane(pane)
        self._refresh_grid_layout()

    def _on_translate_clicked(self):
        if self._thread is not None and self._thread.isRunning():
            return
        self._refresh_jparser_from_source()
        self._refresh_mecab_from_source()
        text = ""
        try:
            text = self.src_edit.toPlainText().strip()
        except Exception:
            return
        if not text:
            return
        jobs = []
        for pane in list(self.grid_order):
            key = getattr(pane, "_engine_key", None)
            if not key or not getattr(pane, "edit", None):
                continue
            pane.edit.setPlainText("..." )
            jobs.append((pane.name, key))
        if not jobs:
            return
        self.btn_translate.setEnabled(False)
        worker = _EngineWorker(jobs, self.src_lang, self.dst_lang, self.config)
        worker.set_text(text)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.one_done.connect(self._on_engine_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_engines_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_engine_done(self, title: str, text: str):
        pane = self.panes.get(title)
        if pane is None:
            pane = next((p for p in self.grid_order if p.name == title), None)
        if pane is not None and getattr(pane, "edit", None):
            pane.edit.setPlainText(text)

    def _on_engines_finished(self):
        self.btn_translate.setEnabled(True)
        self._thread = None
        self._worker = None

    def _refresh_atlas_from_source(self):
        return
