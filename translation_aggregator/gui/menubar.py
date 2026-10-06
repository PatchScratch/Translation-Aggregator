"""Menu bar for the main window.

Ports the original C++ TA menu bar (File / View / Tools / Windows /
Languages) with a modern presentation, minus the Windows-only process
hooking entries that are out of scope for this port:

  File   Translate, Clear source, Quit
  View   Always on top, opacity, column count, lock pane order,
         pane font, show all panes
  Tools  Translate From / To language lists, auto-clipboard,
         romaji->hiragana, substitutions, source text conversions,
         history navigation
  Help   About, project page
"""
from __future__ import annotations

import webbrowser

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMenu

from ..base import Language

OPACITY_STEPS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
GITHUB_URL = "https://github.com/PatchScratch/Translation-Aggregator"


def build_menu_bar(win) -> QMenu:
    from PyQt6.QtWidgets import QMenuBar
    bar = QMenuBar(win)
    _file_menu(win, bar)
    _view_menu(win, bar)
    _tools_menu(win, bar)
    _help_menu(win, bar)
    return bar


def _file_menu(win, bar):
    m = bar.addMenu("&File")

    act = QAction("Translate", win)
    act.setShortcut(QKeySequence("Ctrl+Return"))
    act.triggered.connect(win._on_translate_clicked)
    m.addAction(act)

    act = QAction("Clear Source", win)
    act.setShortcut(QKeySequence("Ctrl+L"))
    act.triggered.connect(lambda: win.src_edit.clear())
    m.addAction(act)

    m.addSeparator()

    act = QAction("Quit", win)
    act.setShortcut(QKeySequence("Ctrl+Q"))
    act.triggered.connect(win.close)
    m.addAction(act)


def _view_menu(win, bar):
    m = bar.addMenu("&View")

    act = QAction("Always on Top", win)
    act.setCheckable(True)
    act.setChecked(bool(getattr(win, "topmost", False)))
    act.toggled.connect(win._toggle_topmost)
    m.addAction(act)

    opacity = m.addMenu("Opacity")
    for value in OPACITY_STEPS:
        a = QAction(f"{int(value * 100)}%", win)
        a.setCheckable(True)
        if abs(getattr(win, "opacity", 1.0) - value) < 0.01:
            a.setChecked(True)
        a.triggered.connect(lambda _=False, v=value: win._set_opacity(v))
        opacity.addAction(a)

    m.addSeparator()

    columns = m.addMenu("Columns")
    for n in (1, 2, 3):
        a = QAction(str(n), win)
        a.setCheckable(True)
        if getattr(win, "n_columns", 2) == n:
            a.setChecked(True)
        a.triggered.connect(lambda _=False, v=n: win._set_column_count(v))
        columns.addAction(a)

    act = QAction("Lock Pane Order", win)
    act.setCheckable(True)
    act.setChecked(bool(getattr(win, "lock_order", False)))
    act.toggled.connect(win._toggle_lock_order)
    m.addAction(act)

    act = QAction("Pane Font…", win)
    act.triggered.connect(win._choose_pane_font)
    m.addAction(act)

    m.addSeparator()

    act = QAction("Show All Panes", win)
    act.triggered.connect(win._show_all_panes)
    m.addAction(act)


def _tools_menu(win, bar):
    m = bar.addMenu("&Tools")

    src = m.addMenu("Translate From")
    dst = m.addMenu("Translate To")
    current_src = str(getattr(win, "src_lang", Language.Japanese))
    current_dst = str(getattr(win, "dst_lang", Language.English))
    for member in Language:
        if member == Language.AUTO:
            a = QAction("Auto-detect", win)
            a.setCheckable(True)
            a.setChecked(current_src == member.value)
            a.triggered.connect(lambda _=False, v=member: win._set_src_lang(v))
            src.addAction(a)
            continue
        a = QAction(_language_label(member), win)
        a.setCheckable(True)
        a.setChecked(current_src == member.value)
        a.triggered.connect(lambda _=False, v=member: win._set_src_lang(v))
        src.addAction(a)

        a2 = QAction(_language_label(member), win)
        a2.setCheckable(True)
        a2.setChecked(current_dst == member.value)
        a2.triggered.connect(lambda _=False, v=member: win._set_dst_lang(v))
        dst.addAction(a2)

    m.addSeparator()

    act = QAction("Auto Clipboard Translation", win)
    act.setCheckable(True)
    if getattr(win, "chk_clip", None) is not None:
        act.setChecked(win.chk_clip.isChecked())
        act.toggled.connect(lambda on: win.chk_clip.setChecked(on))
    m.addAction(act)

    act = QAction("Auto-convert Romaji to Hiragana", win)
    act.setCheckable(True)
    act.setChecked(bool(getattr(win.config, "auto_hiragana", False)))

    def _toggle_hira(on: bool):
        win.config.auto_hiragana = on
        try:
            win.config.save()
        except Exception:
            pass
    act.toggled.connect(_toggle_hira)
    m.addAction(act)

    act = QAction("Substitutions Enabled", win)
    act.setCheckable(True)
    act.setChecked(bool(getattr(win.config, "enable_substitutions", False)))

    def _toggle_sub(on: bool):
        win.config.enable_substitutions = on
        try:
            win.config.save()
        except Exception:
            pass
    act.toggled.connect(_toggle_sub)
    m.addAction(act)

    m.addSeparator()

    conv = m.addMenu("Convert Source Text")
    for label, fn_name in (("To Hiragana", "to_hiragana"),
                           ("To Katakana", "to_katakana"),
                           ("To Romaji", "to_romaji")):
        a = QAction(label, win)
        a.triggered.connect(lambda _=False, f=fn_name: win._convert_source(f))
        conv.addAction(a)

    m.addSeparator()

    act = QAction("Install Playwright (Baidu engine)…", win)
    act.triggered.connect(win._install_playwright_dialog)
    m.addAction(act)

    m.addSeparator()

    act = QAction("History Back", win)
    act.setShortcut(QKeySequence("Alt+Left"))
    act.triggered.connect(win._history_back)
    m.addAction(act)

    act = QAction("History Forward", win)
    act.setShortcut(QKeySequence("Alt+Right"))
    act.triggered.connect(win._history_forward)
    m.addAction(act)

    act = QAction("Clear History", win)
    act.triggered.connect(win._clear_history)
    m.addAction(act)


def _help_menu(win, bar):
    m = bar.addMenu("&Help")

    act = QAction("About Translation Aggregator", win)
    act.triggered.connect(win._about_dialog)
    m.addAction(act)

    act = QAction("Project Page (GitHub)", win)
    act.triggered.connect(lambda: webbrowser.open(GITHUB_URL))
    m.addAction(act)


def _language_label(member: Language) -> str:
    return member.name.replace("_", " ")
