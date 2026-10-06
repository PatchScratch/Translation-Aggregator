"""Color scheme handling for the GUI.

Palette and behaviour mirror the novel-downloader GUI (CustomTkinter,
set_appearance_mode("system")): three choices - System (follow the OS
light/dark setting), Light and Dark - with these colors:

  Dark:  window #2b2b2b, text #dce4ee, accent #1f6aa5, disabled #6e6e6e
  Light: window #fbfbfb, text #1a1a1a, accent #3b8ed0, disabled #a0a0a0
"""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication

SCHEMES = ("system", "light", "dark")
SCHEME_LABELS = {"system": "System", "light": "Light", "dark": "Dark"}

PALETTES = {
    "dark": {
        "window": "#2b2b2b",
        "pane": "#2b2b2b",
        "text": "#dce4ee",
        "disabled": "#6e6e6e",
        "accent": "#1f6aa5",
        "accent_text": "#ffffff",
        "button": "#3a3a3a",
        "button_hover": "#484848",
        "input": "#242424",
        "border": "#555555",
        "handle": "#4a4a4a",
    },
    "light": {
        "window": "#fbfbfb",
        "pane": "#ffffff",
        "text": "#1a1a1a",
        "disabled": "#a0a0a0",
        "accent": "#3b8ed0",
        "accent_text": "#ffffff",
        "button": "#e0e0e0",
        "button_hover": "#d0d0d0",
        "input": "#ffffff",
        "border": "#c0c0c0",
        "handle": "#cccccc",
    },
}

_current = PALETTES["dark"]


def _windows_prefers_light() -> bool:
    """Read the Windows personalization setting (True = light apps)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(value)
    except Exception:
        return False  # unknown: the app has always been dark


def effective_scheme(scheme: str) -> str:
    scheme = (scheme or "system").lower()
    if scheme in ("light", "dark"):
        return scheme
    return "light" if _windows_prefers_light() else "dark"


def palette() -> dict:
    return _current


def pane_qss() -> str:
    p = _current
    return (
        f"TranslatorPane {{ border: 1px solid {p['border']}; "
        f"background-color: {p['pane']}; }}"
    )


def float_window_qss() -> str:
    p = _current
    return (
        f"_PaneFloatWindow {{ border: 1px solid {p['border']}; "
        f"background-color: {p['pane']}; }}"
    )


def _build_qss() -> str:
    p = _current
    return f"""
    QWidget {{ background-color: {p['window']}; color: {p['text']};
              font-size: 10pt; }}
    QLabel:disabled {{ color: {p['disabled']}; }}
    QTextEdit, QPlainTextEdit {{ background-color: {p['input']};
                                color: {p['text']}; border: 1px solid {p['border']}; }}
    QLineEdit {{ background-color: {p['input']}; color: {p['text']};
                border: 1px solid {p['border']}; padding: 2px; }}
    QComboBox {{ background-color: {p['button']}; color: {p['text']};
                border: 1px solid {p['border']}; padding: 2px 6px; }}
    QComboBox QAbstractItemView {{ background-color: {p['window']};
                                  color: {p['text']};
                                  selection-background-color: {p['accent']};
                                  selection-color: {p['accent_text']}; }}
    QPushButton {{ background-color: {p['button']}; color: {p['text']};
                  border: 1px solid {p['border']}; padding: 4px 10px; }}
    QPushButton:hover {{ background-color: {p['button_hover']}; }}
    QPushButton:disabled {{ color: {p['disabled']}; }}
    QCheckBox {{ color: {p['text']}; }}
    QCheckBox:disabled {{ color: {p['disabled']}; }}
    QRadioButton {{ color: {p['text']}; }}
    QGroupBox {{ border: 1px solid {p['border']}; margin-top: 8px;
                color: {p['text']}; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 3px; }}
    QSplitter::handle {{ background-color: {p['handle']}; }}
    QMenuBar {{ background-color: {p['window']}; color: {p['text']}; }}
    QMenu {{ background-color: {p['window']}; color: {p['text']}; }}
    QMenu::item:selected {{ background-color: {p['accent']};
                            color: {p['accent_text']}; }}
    QProgressDialog {{ background-color: {p['window']}; color: {p['text']}; }}
    QToolTip {{ color: #000000; background-color: #ffffe1; }}
    QScrollBar:vertical {{ background: {p['window']}; width: 12px; }}
    QScrollBar::handle:vertical {{ background: {p['handle']};
                                   border-radius: 4px; min-height: 24px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: {p['window']}; height: 12px; }}
    QScrollBar::handle:horizontal {{ background: {p['handle']};
                                      border-radius: 4px; min-width: 24px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    """


def apply_theme(scheme: str) -> str:
    """Apply a scheme app-wide; returns the effective scheme used."""
    global _current
    eff = effective_scheme(scheme)
    _current = PALETTES[eff]
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(_build_qss())
    return eff
