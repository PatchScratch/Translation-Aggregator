"""Stage 1 GUI overlay: web engines + WWWJDIC + OpenAI. No ATLAS."""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QPushButton

from ..engines import TRANSLATOR_MAP, make_translator, DISPLAY_NAMES
from .config_dialog import ConfigDialog
from .engine_config_dialog import ENGINE_CONFIG_DIALOGS
from .window import MainWindow, TranslatorPane


class _EngineWorker(QObject):
    one_done = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, jobs, src, dst, cfg):
        super().__init__()
        self.jobs = jobs
        self.src = src
        self.dst = dst
        self.cfg = cfg
        self._stop = False

    def run(self):
        """Fan out every engine on its own thread; panes fill as each lands.

        Engines are fully independent (fresh translator and HTTP client per
        call), so they translate concurrently. The Playwright-based Baidu
        engine serializes itself onto its persistent-browser thread.
        """
        threads = []
        for title, key in self.jobs:
            if self._stop:
                break
            t = threading.Thread(target=self._run_one, args=(title, key), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        self.finished.emit()

    def _run_one(self, title: str, key: str):
        try:
            eng = make_translator(key, self.cfg)
            res = eng.translate(self.text, src=self.src, dst=self.dst)
            out = (res.error or res.text or "").strip()
        except Exception as e:
            out = str(e)
        self.one_done.emit(title, out)

    def set_text(self, text: str):
        self.text = text


class Stage1Window(MainWindow):
    atlas_done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translation Aggregator")
        self.resize(1600, 950)
        self._engine_keys: list[str] = []
        self._thread = None
        self._worker = None
        self._queued_text = None
        self._add_settings_button()
        self._load_web_engines()
        self._sync_parser_panes()
        self.atlas_done.connect(self._on_atlas_done)

        # menu bar (File / View / Tools / Help) - original TA parity
        from .menubar import build_menu_bar
        self.menu_bar = build_menu_bar(self)
        self.layout().setContentsMargins(4, 0, 4, 4)
        self.layout().insertWidget(0, self.menu_bar)

        # apply persisted view state
        if self.topmost:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowOpacity(self.opacity)
        self._apply_pane_font()

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
        self.refresh_theme()
        self._rebuild_engine_panes()
        self._sync_parser_panes()

    def _rebuild_engine_panes(self):
        # Tear-off windows must go first: their panes rejoin the rebuild,
        # and a stale floating_panes entry would make the fresh pane with
        # the same name unplaceable in any column.
        self._close_float_windows()
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
            has_settings = key in ENGINE_CONFIG_DIALOGS
            pane = TranslatorPane(
                title,
                show_settings=has_settings,
                on_settings=(lambda k=key: self._open_engine_settings(k)) if has_settings else None,
            )
            pane._engine_key = key
            pane._engine = None
            self.panes[title] = pane
            self._register_pane(pane)
        self._refresh_grid_layout()

    def _open_engine_settings(self, key: str):
        """Open the settings dialog for one engine's pane (gear button)."""
        dlg_cls = ENGINE_CONFIG_DIALOGS.get(key)
        if dlg_cls is None:
            return
        dlg = dlg_cls(self, self.config)
        if dlg.exec():
            self.config.save()
            # Engines are built from config on every translate run
            # (make_translator in the worker), so the new values apply
            # on the next translation without rebuilding the panes.

    def _on_translate_clicked(self, from_history: bool = False):
        # record the submission even when a run is busy (idempotent) - but
        # never when we are replaying a history navigation
        if not from_history:
            self._history_push_current()
        if self._thread is not None and self._thread.isRunning():
            # Busy: remember the latest text and translate it when this run
            # finishes, so fast clipboard changes are not dropped.
            self._queued_text = self.src_edit.toPlainText().strip()
            self._queued_from_history = from_history
            return
        self._queued_text = None
        self._queued_from_history = False
        self._refresh_jparser_from_source()
        self._refresh_mecab_from_source()
        self._refresh_atlas_from_source()
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

    def closeEvent(self, event):
        """Stop clipboard watching and join an in-flight engine run.

        Without this, closing mid-translation destroys a QThread that is
        still running, which aborts the process at teardown.
        """
        try:
            self.clipboard_watcher.stop()
        except Exception:
            pass
        thread = getattr(self, "_thread", None)
        worker = getattr(self, "_worker", None)
        if thread is not None and thread.isRunning():
            if worker is not None:
                worker._stop = True
            thread.quit()
            thread.wait(5000)
        self._thread = None
        self._worker = None
        super().closeEvent(event)

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
        queued = getattr(self, "_queued_text", None)
        queued_from_history = getattr(self, "_queued_from_history", False)
        self._queued_text = None
        self._queued_from_history = False
        if queued:
            # A newer text arrived while the last run was in flight
            self._on_translate_clicked(from_history=queued_from_history)

    def _refresh_atlas_from_source(self):
        """ATLAS runs through a 32-bit bridge subprocess (~1-3 s), so do the
        engine work off the UI thread and land the result via a signal."""
        apane = getattr(self, "apane", None)
        if apane is None:
            return
        edit = getattr(apane, "edit", None)
        text = ""
        try:
            text = self.src_edit.toPlainText().strip()
        except Exception:
            return
        if not text:
            if edit:
                edit.setPlainText("")
            return
        try:
            src = (getattr(self, "src_lang", "") or "").lower()
            dst = (getattr(self, "dst_lang", "") or "").lower()
            if src.startswith("ja") and dst.startswith("en"):
                direction = 1
            elif src.startswith("en") and dst.startswith("ja"):
                direction = 2
            else:
                if edit:
                    edit.setPlainText("")
                return
        except Exception:
            return
        if edit:
            edit.setPlainText("...")
        env = (getattr(self.config, "atlas_environment", "General") or "General")
        trs = getattr(self.config, "atlas_trs_path", "") or ""
        flags = int(getattr(self.config, "atlas_flags", 0) or 0)

        def run():
            out = ""
            try:
                atlas = getattr(self, "atlas", None)
                if atlas is not None:
                    atlas.configure(environment=env, trs_path=trs, flags=flags)
                    atlas.set_direction(direction)
                    res = atlas.translate(text)
                    out = res.error or res.text or ""
            except Exception as e:
                out = f"ATLAS error: {e}"
            self.atlas_done.emit(out)

        threading.Thread(target=run, daemon=True, name="atlas-bridge").start()

    def _on_atlas_done(self, text: str):
        apane = getattr(self, "apane", None)
        if apane is not None and getattr(apane, "edit", None) is not None:
            apane.edit.setPlainText(text)
