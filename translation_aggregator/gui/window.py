from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QThread, pyqtSignal as _pyqtSignal, QPoint, QEvent, QSize, QRect
from PyQt6.QtGui import QTextCursor, QClipboard, QAction, QDrag, QPainter, QFont, QFontMetrics, QColor, QPen, QTextCharFormat
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QToolBar, QPushButton,
    QLabel, QSplitter, QCheckBox, QApplication, QMenuBar, QMenu, QSizePolicy,
    QMessageBox, QProgressDialog, QToolTip
)
from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen
from PyQt6.QtCore import QRect
from pathlib import Path
import requests
import gzip
import shutil

from ..base import Language, TranslationResult
from ..translators import GoogleTranslator, BingTranslator, DeepLTranslator, BaiduTranslator, BaiduPlaywrightTranslator, YandexTranslator
from ..jparser import JParser, to_romaji, to_hiragana, to_katakana

# --- Ruby display widget for JParser (readings directly above Japanese words) ---
class JParserRubyWidget(QWidget):
    """Draws Japanese words with their readings (in chosen furigana script) as ruby above each word.
    Hover shows the parser detail (gloss) in a tooltip bubble.
    Respects JParser font sizes and basic color settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments: list[tuple[str, str, str]] = []   # (reading, japanese, detail)
        self._seg_rects: list[tuple[int, int, int, int, int]] = []  # (x, y, w, h, idx)
        self._hover_idx = -1
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(40)
        # Force white background so JParser highlight colors (and default black text) are visible
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor("white"))
        self.setPalette(pal)
        self.setStyleSheet("background-color: white;")

    def set_segments(self, segments):
        # Always normalize to list of (reading, jap, gloss, color_hex_or_None)
        norm = []
        for s in (segments or []):
            try:
                if isinstance(s, (list, tuple)):
                    rd = s[0] if len(s) > 0 else ""
                    jp = s[1] if len(s) > 1 else ""
                    gl = s[2] if len(s) > 2 else ""
                    col = s[3] if len(s) > 3 else None
                    norm.append((rd, jp, gl, col))
            except Exception:
                pass
        self.segments = norm
        self._seg_rects = []
        self._hover_idx = -1
        self.update()

    def sizeHint(self):
        return QSize(400, 52)

    def _get_fonts(self):
        base = QFont(self.font())
        try:
            n = int(getattr(config, "jparser_font_size_normal", 11) or 11)
            f = int(getattr(config, "jparser_font_size_furigana", 8) or 8)
        except Exception:
            n, f = 11, 8
        base.setPointSize(max(7, n))
        ruby = QFont(base)
        ruby.setPointSize(max(5, f))
        return base, ruby

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Ensure white background so configured highlight colors (kanji/kana/particles/translated etc.) are visible
        p.fillRect(self.rect(), QColor("white"))

        base_font, ruby_font = self._get_fonts()
        fm_r = QFontMetrics(ruby_font)
        fm_j = QFontMetrics(base_font)

        # Colors from config (fall back to readable defaults on white background)
        try:
            c_default = QColor("#" + getattr(config, "jparser_color_default", "000000"))
            c_furi    = QColor("#" + getattr(config, "jparser_color_furigana", "000000"))
        except Exception:
            c_default = QColor("#000000")
            c_furi    = QColor("#000000")

        margin = 3
        gap = 2
        x = margin
        y_ruby = margin + fm_r.ascent()
        y_jap  = y_ruby + fm_r.descent() + gap + fm_j.ascent()

        self._seg_rects = []
        for i, (rd, jp, det, col) in enumerate(self.segments):
            rw = fm_r.horizontalAdvance(rd or "")
            jw = fm_j.horizontalAdvance(jp or "")
            w = max(rw, jw) + 4
            h = fm_j.height()

            # Draw highlight background tint using the per-word color (on white this makes highlights visible).
            # Japanese text itself is drawn in the default color (readable on white).
            if col:
                try:
                    bg = QColor("#" + str(col).lstrip("#"))
                    bg.setAlpha(90)  # visible but subtle tint on white
                    p.fillRect(x, y_jap - fm_j.ascent() - 1, w, h + 2, bg)
                except Exception:
                    pass

            # ruby (reading) uses furigana color from config
            p.setFont(ruby_font)
            p.setPen(c_furi)
            p.drawText(x + (w - rw)//2, y_ruby, rd or "")

            # Japanese word in default color (black or configured default) so it is always readable
            p.setFont(base_font)
            p.setPen(c_default)
            p.drawText(x + (w - jw)//2, y_jap, jp or "")

            self._seg_rects.append((x, y_jap - fm_j.ascent(), w, h, i))
            x += w + 6

        p.end()
        total_h = y_jap + fm_j.descent() + margin
        if self.height() != total_h:
            self.setFixedHeight(total_h)

    def _seg_at(self, pos: QPoint) -> int:
        for x,y,w,h,idx in self._seg_rects:
            if QRect(x, y, w, h).contains(pos):
                return idx
        return -1

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self._seg_at(pos)
        if idx != self._hover_idx:
            self._hover_idx = idx
            if 0 <= idx < len(self.segments):
                tip = self.segments[idx][2] or ""
                QToolTip.showText(self.mapToGlobal(pos), tip, self)
            else:
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_idx = -1
        QToolTip.hideText()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        # Allow copying the plain Japanese sentence
        from PyQt6.QtWidgets import QMenu, QApplication
        m = QMenu(self)
        act = m.addAction("Copy Japanese sentence")
        act.triggered.connect(lambda: QApplication.clipboard().setText(''.join(s[1] for s in self.segments)))
        m.exec(event.globalPos())


# --- MeCab pane widget: faithful port of MecabWindow.cpp rendering ---
class MecabRubyWidget(QWidget):
    """Displays MeCab tokenization with readings (furigana) above each surface.
    Matches the original TA MeCab pane behavior (MecabWindow.cpp).
    Respects config.mecab_furigana (hiragana | katakana | romaji | none).
    Hover tooltip shows the full MeCab feature line (or POS).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tokens: list[tuple[str, str, str]] = []  # (reading, surface, detail)
        self._seg_rects: list[tuple[int, int, int, int, int]] = []
        self._hover_idx = -1
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(60)

    def set_tokens(self, tokens: list[tuple[str, str, str]]):
        self.tokens = list(tokens or [])
        self._seg_rects = []
        self._hover_idx = -1
        self.update()

    def _get_fonts(self):
        base = QFont(self.font())
        try:
            n = int(getattr(config, "mecab_font_size_normal", 13) or 13)
            f = int(getattr(config, "mecab_font_size_furigana", 10) or 10)
        except Exception:
            n, f = 13, 10
        base.setPointSize(max(7, n))
        ruby = QFont(base)
        ruby.setPointSize(max(5, f))
        return base, ruby

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(self.rect(), QColor("white"))

        base_font, ruby_font = self._get_fonts()
        fm_r = QFontMetrics(ruby_font)
        fm_s = QFontMetrics(base_font)

        mode = (getattr(config, "mecab_furigana", "hiragana") or "hiragana").lower()

        # Colors from MeCab config (fallbacks match the dialog defaults)
        try:
            c_default  = QColor("#" + getattr(config, "mecab_color_default", "80F9FF"))
            c_furi     = QColor("#" + getattr(config, "mecab_color_furigana", "E0DE00"))
            c_part     = QColor("#" + getattr(config, "mecab_color_particles", "E0DEFF"))
        except Exception:
            c_default = QColor("#80F9FF")
            c_furi    = QColor("#E0DE00")
            c_part    = QColor("#E0DEFF")

        common_particles = {"の","は","が","を","に","で","と","も","から","まで","へ","や","か","よ","ね","な","わ","ぞ","ぜ","ば","が","を"}

        margin = 3
        gap = 2
        x = margin
        y_ruby = margin + fm_r.ascent()
        y_surf = y_ruby + fm_r.descent() + gap + fm_s.ascent()

        self._seg_rects = []
        for i, item in enumerate(self.tokens):
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                rd, surf, det = item[0], item[1], item[2]
            else:
                rd, surf, det = "", "", ""

            rtext = ""
            if mode == "hiragana":
                rtext = to_hiragana(rd or "")
            elif mode == "katakana":
                rtext = to_katakana(rd or "")
            elif mode == "romaji":
                rtext = to_romaji(rd or "")

            rw = fm_r.horizontalAdvance(rtext or "")
            sw = fm_s.horizontalAdvance(surf or "")
            w = max(rw, sw) + 4
            h = fm_s.height()

            # Decide highlight color for this token (background tint like JParser pane)
            det_l = (det or "").lower()
            is_particle = (surf in common_particles) or "(prt)" in det_l or "助詞" in det or "particle" in det_l
            if is_particle:
                hl = c_part
            elif rtext:
                hl = c_furi
            else:
                hl = c_default

            # subtle background tint for the word
            try:
                bg = QColor(hl)
                bg.setAlpha(80)
                p.fillRect(x, y_surf - fm_s.ascent() - 1, w, h + 2, bg)
            except Exception:
                pass

            if rtext:
                p.setFont(ruby_font)
                p.setPen(QColor("#000000"))
                p.drawText(x + (w - rw)//2, y_ruby, rtext)

            p.setFont(base_font)
            p.setPen(QColor("#000000"))
            p.drawText(x + (w - sw)//2, y_surf, surf or "")

            self._seg_rects.append((x, y_surf - fm_s.ascent(), w, h, i))
            x += w + 6

        p.end()
        total_h = y_surf + fm_s.descent() + margin
        if self.height() != total_h:
            self.setFixedHeight(total_h)

    def _seg_at(self, pos: QPoint) -> int:
        for x, y, w, h, idx in self._seg_rects:
            if QRect(x, y, w, h).contains(pos):
                return idx
        return -1

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self._seg_at(pos)
        if idx != self._hover_idx:
            self._hover_idx = idx
            if 0 <= idx < len(self.tokens):
                tip = self.tokens[idx][2] or ""
                QToolTip.showText(self.mapToGlobal(pos), tip, self)
            else:
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_idx = -1
        QToolTip.hideText()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu, QApplication
        m = QMenu(self)
        act = m.addAction("Copy MeCab surface text")
        act.triggered.connect(lambda: QApplication.clipboard().setText(''.join(t[1] for t in self.tokens)))
        m.exec(event.globalPos())


from ..mecab import MecabWrapper
from ..atlas import AtlasEngine
from ..config import config
from ..history import HistoryStore


TRANSLATOR_MAP = {
    "google": GoogleTranslator,
    "bing": BingTranslator,
    "deepl": DeepLTranslator,
    "baidu": BaiduTranslator,
    "baidu_pw": BaiduPlaywrightTranslator,
    "yandex": YandexTranslator,
}


class TranslatorPane(QWidget):
    def __init__(self, name: str, parent=None, show_settings: bool = False, on_settings=None):
        super().__init__(parent)
        self.name = name
        self.setLayout(QVBoxLayout())

        # Header first (title bar on top)
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(2, 2, 2, 2)
        hl.setSpacing(4)
        self.label = QLabel(name)
        self.label.setStyleSheet("font-weight: bold; padding: 2px;")
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        hl.addWidget(self.label)

        if show_settings:
            self.gear_btn = QPushButton("⚙")
            self.gear_btn.setFixedSize(18, 18)
            self.gear_btn.setFlat(True)
            self.gear_btn.setStyleSheet(
                "QPushButton { font-size: 11pt; padding: 0; border: none; }"
                "QPushButton:hover { color: #4a90e2; }"
            )
            self.gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if on_settings:
                self.gear_btn.clicked.connect(on_settings)
            hl.addWidget(self.gear_btn)

        hl.addStretch(1)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setStyleSheet(
            "QPushButton { border: none; font-size: 10pt; padding: 0; }"
            "QPushButton:hover { color: #ff5555; }"
        )
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._close_clicked)
        hl.addWidget(self.close_btn)
        if self.name in ("JParser", "MeCab", "ATLAS"):
            self.close_btn.hide()
        else:
            self.close_btn.show()
        self.layout().addWidget(header)
        self.header = header

        if self.name == "JParser":
            # Use ruby widget for classic look: readings above Japanese words, hover for gloss
            self.jp_ruby = JParserRubyWidget()
            self.jp_ruby.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            # Force white background so JParser highlight colors (kanji/kana/translated/particles etc.) are visible
            self.jp_ruby.setAutoFillBackground(True)
            pal = self.jp_ruby.palette()
            pal.setColor(self.jp_ruby.backgroundRole(), QColor("white"))
            self.jp_ruby.setPalette(pal)
            self.jp_ruby.setStyleSheet("background-color: white;")
            self.layout().addWidget(self.jp_ruby)
            self.edit = None
            self.layout().setStretch(0, 0)
            self.layout().setStretch(1, 0)
        elif self.name == "MeCab":
            # Faithful MeCab pane: tokenized output with readings (hiragana default), matching MecabWindow.cpp
            self.mecab_ruby = MecabRubyWidget()
            self.mecab_ruby.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.mecab_ruby.setAutoFillBackground(True)
            pal = self.mecab_ruby.palette()
            pal.setColor(self.mecab_ruby.backgroundRole(), QColor("white"))
            self.mecab_ruby.setPalette(pal)
            self.mecab_ruby.setStyleSheet("background-color: white;")
            self.layout().addWidget(self.mecab_ruby)
            self.edit = None
            self.layout().setStretch(0, 0)
            self.layout().setStretch(1, 1)
        else:
            # IMPORTANT: The result text box must be created for every pane.
            self.edit = QTextEdit()
            self.edit.setReadOnly(True)
            self.edit.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse |
                Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            self.edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.edit.setMinimumHeight(48)
            self.layout().addWidget(self.edit)
            self.layout().setStretch(0, 0)
            self.layout().setStretch(1, 1)

        # The whole pane can be resized vertically by its parent splitter
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(60)

        # Make the title label transparent so mouse reaches the header for dragging
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Drag handle on the header
        self.header.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start_pos = None

        _self = self

        def _press(e):
            if e.button() == Qt.MouseButton.LeftButton:
                _self._drag_start_pos = e.position().toPoint()
                _self._select_self()

        def _move(e):
            if not getattr(_self, '_drag_start_pos', None):
                return
            if (e.position().toPoint() - _self._drag_start_pos).manhattanLength() < 8:
                return
            d = QDrag(_self)
            m = QMimeData()
            m.setText("pane:" + _self.name)
            d.setMimeData(m)
            d.exec(Qt.DropAction.MoveAction)
            _self._drag_start_pos = None

        def _release(e):
            _self._drag_start_pos = None

        self.header.mousePressEvent = _press
        self.header.mouseMoveEvent = _move
        self.header.mouseReleaseEvent = _release

        # Accept drops on the pane and its children (so you can drop over the text area or header)
        self.setAcceptDrops(True)
        if self.edit:
            self.edit.setAcceptDrops(True)
        self.header.setAcceptDrops(True)

        # Forward drops from children to this pane's handlers
        if self.edit:
            self.edit.dragEnterEvent = self.dragEnterEvent
            self.edit.dragMoveEvent = self.dragMoveEvent
            self.edit.dropEvent = self.dropEvent
        self.header.dragEnterEvent = self.dragEnterEvent
        self.header.dragMoveEvent = self.dragMoveEvent
        self.header.dropEvent = self.dropEvent

        # Panes are hidden until _refresh_grid_layout places them inside column splitters
        self.setVisible(False)

        self.last_result = None
        self._selected = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Visible border so the edges of each pane are clear and draggable via the splitter handles next to them
        self.setStyleSheet("TranslatorPane { border: 1px solid #555; background-color: #2b2b2b; }")

        # Also allow clicking the label area to select
        self.label.mousePressEvent = self._label_clicked

        self.last_result: TranslationResult | None = None
        self._selected = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # JParser sentence view: romaji on top, Japanese sentence below, hover details
        self._jp_romaji_line: str = ""
        self._jp_jap_sentence: str = ""
        self._jp_ranges: list[tuple[int, int, int]] = []  # (start, end, detail_idx) in jap_sentence
        self._jp_detail_list: list[str] = []
        if self.edit and self.name != "JParser":
            self.edit.viewport().installEventFilter(self)

    def _label_clicked(self, event):
        self._select_self()

    def mousePressEvent(self, event):
        self._select_self()
        super().mousePressEvent(event)

    def _select_self(self):
        parent = self
        while parent and not hasattr(parent, "select_pane"):
            parent = parent.parent()
        if parent and hasattr(parent, "select_pane"):
            parent.select_pane(self)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setStyleSheet("")
        if self.name in ("JParser", "MeCab", "ATLAS"):
            self.label.setText(self.name)
            self.close_btn.hide()
            return
        self.label.setText(self.name)
        self.close_btn.show()

    def _close_clicked(self):
        parent = self
        while parent and not hasattr(parent, "clear_pane_selection"):
            parent = parent.parent()
        if parent and hasattr(parent, "clear_pane_selection"):
            parent.clear_pane_selection(self)
        else:
            self.set_selected(False)

    def set_result(self, res: TranslationResult):
        self.last_result = res
        if self.name == "JParser":
            # JParser pane uses the ruby widget for display + hover bubble.
            # set_result is only used for error clearing here.
            if res.error and hasattr(self, "jp_ruby") and self.jp_ruby:
                self.jp_ruby.set_segments([])
            return

        if self.name == "MeCab":
            # MeCab pane uses its own ruby widget (MecabRubyWidget).
            # set_result is only used for error clearing here.
            if res.error and hasattr(self, "mecab_ruby") and self.mecab_ruby:
                self.mecab_ruby.set_tokens([])
            return

        if res.error:
            if self.edit:
                self.edit.setPlainText(f"[ERROR] {res.error}")
            return

        if not self.edit:
            return

        text = res.text or ""
        self.edit.setPlainText(text)

    def set_jp_sentence(self, romaji: str, japanese: str, ranges: list[tuple[int, int, int]], details: list[str]):
        # Legacy for old edit-based JParser view. Ruby widget does not use this.
        pass

    def _apply_jparser_font_sizes(self):
        """JParser pane now uses JParserRubyWidget (paint reads config live).
        This method is kept for compatibility with old edit-based path only."""
        if self.name != "JParser" or not self.edit:
            return
        # Ruby widget path: no edit, sizes applied on next paint via config
        return

    def eventFilter(self, watched, event):
        # JParser pane now uses ruby widget for display; skip old edit tooltip filter
        if self.name == "JParser":
            return super().eventFilter(watched, event)
        if self.name == "JParser" and self.edit and watched is self.edit.viewport():
            if event.type() == QEvent.Type.MouseMove:
                self._jp_show_tooltip(event.position().toPoint())
            elif event.type() == QEvent.Type.Leave:
                QToolTip.hideText()
        return super().eventFilter(watched, event)

    def _jp_show_tooltip(self, local_pos: QPoint):
        # Legacy path for old edit-based JParser view. Ruby widget handles its own hover.
        QToolTip.hideText()

    # --- Drag & drop support for reordering panes inside the column grid ---

    # Note: actual header drag handlers are set in __init__ using closures that capture self.
    # The methods below are intentionally left (or removed) to avoid confusion.

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("pane:"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        # Required for the drop to be allowed when dragging over the pane (or its children)
        if event.mimeData().hasText() and event.mimeData().text().startswith("pane:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        txt = event.mimeData().text()
        if not txt.startswith("pane:"):
            event.ignore()
            return
        src_name = txt[5:]
        mw = self._find_main_window()
        if mw:
            # Use global cursor position mapped to this pane for a reliable before/after decision.
            # This works even when the drop event was forwarded from the QTextEdit or header child.
            try:
                from PyQt6.QtGui import QCursor
                gpos = QCursor.pos()
                local = self.mapFromGlobal(gpos)
                y = local.y()
            except Exception:
                # Fallback: use the event position as-is (may be slightly off if from child)
                y = event.position().toPoint().y()
            if y > self.height() // 2:
                mw.move_pane_after(src_name, self.name)
            else:
                mw.move_pane_before(src_name, self.name)
        event.acceptProposedAction()

    def _find_main_window(self):
        p = self
        while p:
            if isinstance(p, MainWindow):
                return p
            p = p.parent()
        return None


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translation Aggregator (Python)")
        self.resize(1100, 700)

        self.config = config
        self.history = HistoryStore()

        self.src_lang = Language.Japanese
        self.dst_lang = Language.English

        self.clipboard_watcher = QTimer(self)
        self.clipboard_watcher.timeout.connect(self._check_clipboard)
        self.last_clipboard = ""
        self.auto_clip = True

        self.translators = []
        self.panes: dict[str, TranslatorPane] = {}

        # Selection / grid state must exist before _build_ui (which calls _rebuild_columns)
        self.selected_panes: set[TranslatorPane] = set()
        self.pane_list: list[TranslatorPane] = []
        self.grid_order: list[TranslatorPane] = []
        # column_contents[c] is the ordered list of panes currently in column c.
        # This is the source of truth for layout and drag-drop placement.
        self.column_contents: list[list[TranslatorPane]] = []

        self._build_ui()
        self._load_translators()

        # JParser + Mecab + Atlas
        self.jparser = JParser()
        self.mecab = None
        try:
            self.mecab = MecabWrapper()
        except Exception:
            pass
        self.atlas = AtlasEngine()

        self.jpane = TranslatorPane("JParser", show_settings=True, on_settings=self._open_jparser_settings)
        self.mpane = TranslatorPane("MeCab", show_settings=True, on_settings=self._open_mecab_settings)
        self.apane = TranslatorPane("ATLAS", show_settings=True, on_settings=self._open_atlas_settings)
        for p in (self.jpane, self.mpane, self.apane):
            if p not in self.grid_order:
                self.grid_order.append(p)
            self._register_pane(p)
        self._refresh_grid_layout()

        # Minimum height + font sizes for the JParser pane (ruby widget or edit)
        self.jpane.setMinimumHeight(80)
        if getattr(self.jpane, "jp_ruby", None):
            pass
        elif getattr(self.jpane, "edit", None):
            pass  # ruby widget path has no edit

        self._apply_jparser_font_sizes()

        # 100% port of ATLAS pane initialization (AtlasWindow.cpp)
        # Apply saved config (environment, rule set, flags) + direction (only ja<->en supported)
        self._apply_atlas_config()

    def _build_ui(self):
        """Build the main window UI: source text + Translate button at top, then nested splitters for panes."""
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Top row: source editor + Translate button (JParser only)
        top = QHBoxLayout()
        self.src_edit = QTextEdit()
        self.src_edit.setPlaceholderText("Paste or type Japanese text here...")
        self.src_edit.setAcceptRichText(False)
        self.src_edit.setMaximumHeight(90)
        top.addWidget(self.src_edit, 1)

        self.btn_translate = QPushButton("Translate")
        self.btn_translate.setFixedWidth(90)
        self.btn_translate.clicked.connect(self._on_translate_clicked)
        top.addWidget(self.btn_translate, 0)

        root.addLayout(top)

        # Content area uses nested splitters (vertical for src vs columns, horizontal for columns)
        self.content_splitter = QSplitter(Qt.Orientation.Vertical)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(8)

        self.columns_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.columns_splitter.setChildrenCollapsible(False)
        self.columns_splitter.setHandleWidth(8)

        # The actual panes will be placed into column splitters by _refresh_grid_layout
        self.content_splitter.addWidget(self.columns_splitter)
        root.addWidget(self.content_splitter, 1)

        # Store references used elsewhere
        self._src_label = None  # not used, kept for compatibility

    def _on_translate_clicked(self):
        """Manual trigger: feed source to JParser, MeCab and ATLAS panes (100% ports)."""
        self._refresh_jparser_from_source()
        self._refresh_mecab_from_source()
        self._refresh_atlas_from_source()

    def _refresh_jparser_from_source(self):
        """Parse the current source text with JParser and display ruby + hover gloss (faithful port)."""
        if not hasattr(self, "jpane") or not self.jpane:
            return
        text = ""
        try:
            if getattr(self, "src_edit", None):
                text = self.src_edit.toPlainText().strip()
        except Exception:
            return
        if not text:
            if hasattr(self.jpane, "jp_ruby") and self.jpane.jp_ruby:
                self.jpane.jp_ruby.set_segments([])
            return
        try:
            matches = self.jparser.parse(text)
            segments = []
            mode = getattr(self.jparser, "furigana_mode", "romaji") or "romaji"
            prev_start = None
            for m in matches:
                if prev_start is not None and getattr(m, 'start', None) == prev_start:
                    continue
                prev_start = getattr(m, 'start', None)
                raw = getattr(m, "reading", "") or getattr(m, "jap", "")
                if hasattr(self.jparser, "_format_reading"):
                    r = self.jparser._format_reading(raw)
                else:
                    r = to_romaji(raw)
                if mode == "none":
                    r = ""
                jp = getattr(m, "jap", "")
                raw_gloss = getattr(m, "gloss", "") or ""
                conj = getattr(m, "conj", None) or []
                gloss = self.jparser.format_gloss(raw_gloss, conj) if hasattr(self.jparser, "format_gloss") else (raw_gloss[:120])

                flags = getattr(m, "jap_flags", 0) or 0
                has_kanji = any("\u4e00" <= c <= "\u9fbf" for c in jp)
                has_conj = bool(conj)
                gloss_l = (raw_gloss or "").lower()
                is_particle = bool(flags & 0x0010) or "(prt)" in gloss_l or "(aux)" in gloss_l or jp in ("の","は","が","を","に","で","と","も","から","まで","へ","や","か","よ","ね","な","わ","ぞ","ぜ","ば")
                if is_particle:
                    color = getattr(config, "jparser_color_particles", "E0E0FF")
                elif has_kanji:
                    color = getattr(config, "jparser_color_kanji", "A00000")
                elif has_conj:
                    color = getattr(config, "jparser_color_conjugations", "969696")
                else:
                    color = getattr(config, "jparser_color_kana", "1EA01E")
                segments.append((r, jp, gloss, color))
                if len(segments) >= 80:
                    break
            if hasattr(self.jpane, "jp_ruby") and self.jpane.jp_ruby:
                self.jpane.jp_ruby.set_segments(segments)
        except Exception:
            pass

    def _refresh_mecab_from_source(self):
        """Parse current source with MeCab and display tokenized output (faithful to MecabWindow.cpp)."""
        if not hasattr(self, "mpane") or not self.mpane:
            return
        text = ""
        try:
            if getattr(self, "src_edit", None):
                text = self.src_edit.toPlainText().strip()
        except Exception:
            return
        ruby = getattr(self.mpane, "mecab_ruby", None)
        if not text:
            if ruby:
                ruby.set_tokens([])
            return
        if not getattr(self, "mecab", None):
            if ruby:
                ruby.set_tokens([("", "[MeCab not available]", "Install mecab or mecab-python3")])
            return
        try:
            raw_tokens = self.mecab.parse_to_tokens(text) or []
            segments = []
            for t in raw_tokens:
                surf = t.get("surface", "")
                mecab_rd = t.get("reading") or t.get("pron") or surf
                lookup_keys = []
                if t.get("lemma"):
                    lookup_keys.append(t["lemma"])
                if surf and surf not in lookup_keys:
                    lookup_keys.append(surf)
                cands = []
                if hasattr(self, "jparser") and hasattr(self.jparser, "_lookup_surface"):
                    for k in lookup_keys:
                        got = self.jparser._lookup_surface(k) or []
                        for e in got:
                            key = (e.get("reading"), (e.get("gloss") or "")[:60])
                            if key not in [(x.get("reading"), (x.get("gloss") or "")[:60]) for x in cands]:
                                cands.append(e)
                mr = to_hiragana(mecab_rd or surf)
                ordered = []
                for e in cands:
                    if to_hiragana(e.get("reading", "") or "") == mr:
                        ordered.insert(0, e)
                    else:
                        ordered.append(e)
                if not ordered:
                    ordered = list(cands)
                detail_lines = []
                for e in ordered:
                    rd = e.get("reading") or surf
                    raw_gloss = e.get("gloss", "") or ""
                    g = raw_gloss.strip("/")
                    if "/Ent" in g:
                        g = g.split("/Ent", 1)[0]
                    g = g.strip("/")
                    detail_lines.append(f"{surf}【{rd}】 {g}")
                if not detail_lines:
                    detail_lines.append(t.get("raw", t.get("pos", surf) or surf))
                detail = "\n".join(detail_lines)
                segments.append((mecab_rd or surf, surf, detail))
            if ruby:
                ruby.set_tokens(segments)
        except Exception as e:
            if ruby:
                ruby.set_tokens([("", "[MeCab error]", str(e))])

    def _apply_atlas_config(self):
        """Push current ATLAS settings from config into the engine (exact port of original setup)."""
        if not hasattr(self, "atlas") or not self.atlas:
            return
        env = getattr(self.config, "atlas_environment", "General") or "General"
        trs = getattr(self.config, "atlas_trs_path", "") or ""
        flags = int(getattr(self.config, "atlas_flags", 0) or 0)
        try:
            self.atlas.configure(environment=env, trs_path=trs, flags=flags)
        except Exception:
            pass

        # Direction: only ja<->en is supported (exact match to CanTranslate in AtlasWindow)
        try:
            src = (getattr(self, "src_lang", "") or "").lower()
            dst = (getattr(self, "dst_lang", "") or "").lower()
            if src.startswith("ja") and dst.startswith("en"):
                self.atlas.set_direction(1)  # ja->en
            elif src.startswith("en") and dst.startswith("ja"):
                self.atlas.set_direction(2)  # en->ja
        except Exception:
            pass

    def _refresh_atlas_from_source(self):
        """Feed current source to ATLAS pane (faithful to AtlasWindow.cpp Translate + TryStartTask)."""
        if not hasattr(self, "apane") or not self.apane:
            return
        edit = getattr(self.apane, "edit", None)
        text = ""
        try:
            if getattr(self, "src_edit", None):
                text = self.src_edit.toPlainText().strip()
        except Exception:
            pass

        if not text:
            if edit:
                edit.setPlainText("")
            return

        # Only ja<->en is supported (exact port of CanTranslate)
        try:
            src = (getattr(self, "src_lang", "") or "").lower()
            dst = (getattr(self, "dst_lang", "") or "").lower()
            can = (src.startswith("ja") and dst.startswith("en")) or (src.startswith("en") and dst.startswith("ja"))
        except Exception:
            can = False

        if not can:
            if edit:
                edit.setPlainText("")
            return

        if not getattr(self, "atlas", None):
            if edit:
                # Match original behavior when InitAtlas fails.
                # On 64-bit Python we expect the bridge path.
                if getattr(self, "atlas", None) and getattr(self.atlas, "is_using_bridge", False):
                    edit.setPlainText("Failed to initialize Fujitsu ATLAS v14.\nATLAS requires a 32-bit Python (using bridge). Set TA_ATLAS_32_PYTHON or install/register a 32-bit Python.")
                else:
                    edit.setPlainText("Failed to initialize Fujitsu ATLAS v14.")
            return

        # Detect bridge usage (64-bit host talking to 32-bit ATLAS via subprocess).
        # This is the supported future-proof path when the main Python is 64-bit.
        using_bridge = False
        try:
            using_bridge = bool(self.atlas.is_using_bridge)
        except Exception:
            pass

        # Apply latest config (environment, rule set, flags) before each run
        self._apply_atlas_config()

        try:
            res = self.atlas.translate(text)
            if edit:
                if res.error:
                    if using_bridge:
                        # ALWAYS show the complete output from the 32-bit bridge on error.
                        # The bridge now includes the exact command it tried + full stderr + stdout.
                        full = res.error
                        try:
                            if getattr(self.atlas, "last_error", None):
                                if self.atlas.last_error not in full:
                                    full += "\n" + self.atlas.last_error
                        except Exception:
                            pass
                        edit.setPlainText("[via 32-bit ATLAS bridge]\n" + full)
                    else:
                        edit.setPlainText(res.error)
                else:
                    if using_bridge:
                        edit.setPlainText("[via 32-bit ATLAS bridge]\n" + (res.text or ""))
                    else:
                        edit.setPlainText(res.text or "")
        except Exception as e:
            if edit:
                edit.setPlainText(str(e))

    def _check_clipboard(self):
        """Auto-clipboard watcher: feeds JParser only."""
        try:
            clip = QApplication.clipboard().text()
        except Exception:
            return
        if not clip or clip == self.last_clipboard:
            return
        self.last_clipboard = clip
        if not self.auto_clip:
            return
        try:
            if getattr(self, "src_edit", None):
                self.src_edit.setPlainText(clip)
        except Exception:
            pass
        self._refresh_jparser_from_source()

    def _load_translators(self):
        """Stub: real implementation populates self.translators from config."""
        self.translators = []

    def _register_pane(self, pane: "TranslatorPane"):
        if pane not in self.pane_list:
            self.pane_list.append(pane)
        if pane not in self.grid_order:
            self.grid_order.append(pane)

    def _refresh_grid_layout(self):
        """Place panes into the column splitters (round-robin across visible columns)."""
        # Ensure we have at least one column splitter
        while self.columns_splitter.count() < 1:
            col = QSplitter(Qt.Orientation.Vertical)
            col.setChildrenCollapsible(False)
            col.setHandleWidth(6)
            self.columns_splitter.addWidget(col)

        # For simplicity in this minimal build: put all grid_order panes into the first column
        col0 = self.columns_splitter.widget(0)
        # Clear existing
        while col0.count():
            w = col0.widget(0)
            col0.removeWidget(w)
            w.setParent(None)
        for p in self.grid_order:
            col0.addWidget(p)
            p.setVisible(True)
            p.show()

    def _rebuild_columns(self):
        self._refresh_grid_layout()

    def select_pane(self, pane):
        self.selected_panes.add(pane)
        if hasattr(pane, "set_selected"):
            pane.set_selected(True)

    def clear_pane_selection(self, pane):
        if pane in self.selected_panes:
            self.selected_panes.remove(pane)
        if hasattr(pane, "set_selected"):
            pane.set_selected(False)

    def move_pane_before(self, src_name: str, dst_name: str):
        self._move_pane_relative(src_name, dst_name, before=True)

    def move_pane_after(self, src_name: str, dst_name: str):
        self._move_pane_relative(src_name, dst_name, before=False)

    def _move_pane_relative(self, src_name: str, dst_name: str, before: bool):
        src = next((p for p in self.grid_order if p.name == src_name), None)
        dst = next((p for p in self.grid_order if p.name == dst_name), None)
        if not src or not dst or src is dst:
            return
        self.grid_order.remove(src)
        idx = self.grid_order.index(dst)
        if not before:
            idx += 1
        self.grid_order.insert(idx, src)
        self._refresh_grid_layout()

    def _apply_jparser_font_sizes(self):
        # Delegate to the pane if it has the old edit-based applicator (no-op for ruby widget)
        if hasattr(self, "jpane") and hasattr(self.jpane, "_apply_jparser_font_sizes"):
            self.jpane._apply_jparser_font_sizes()

    def _open_jparser_settings(self):
        from .jparser_config_dialog import JParserConfigDialog
        dlg = JParserConfigDialog(self, self.config)
        if dlg.exec():
            self.config.save()
            self.jparser = JParser()
        self._refresh_jparser_from_source()
        self._refresh_mecab_from_source()
        self._refresh_atlas_from_source()
        self._refresh_atlas_from_source()

    def _open_mecab_settings(self):
        from .mecab_config_dialog import MecabConfigDialog
        dlg = MecabConfigDialog(self, self.config)
        if dlg.exec():
            self.config.save()
        # refresh MeCab pane with new settings (font size + furigana + colors)
        self._refresh_mecab_from_source()

    def _open_atlas_settings(self):
        from .atlas_config_dialog import AtlasConfigDialog
        dlg = AtlasConfigDialog(self, self.config)
        if dlg.exec():
            self.config.save()
        self._apply_atlas_config()
        self._refresh_atlas_from_source()

    def download_edict2(self):
        """Download edict2.gz from the official site into the configured dictionaries directory."""
        target_dir = Path(self.config.dictionaries_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "edict2.gz"
        url = "http://ftp.edrdg.org/pub/Nihongo/edict2.gz"

        dlg = QProgressDialog("Downloading edict2.gz...", "Cancel", 0, 0, self)
        dlg.setWindowTitle("edict2")
        dlg.setModal(True)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)

        # Track user-initiated cancel only via the signal.
        cancelled = [False]
        dlg.canceled.connect(lambda: cancelled.__setitem__(0, True))

        dlg.show()
        QApplication.processEvents()
        QApplication.processEvents()

        try:
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()

            if cancelled[0]:
                dlg.close()
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass
                QMessageBox.information(self, "Cancelled", "Download cancelled.")
                return

            total = int(resp.headers.get("Content-Length", 0) or 0)
            if total > 0:
                dlg.setMaximum(total)

            downloaded = 0
            with open(target, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if cancelled[0]:
                        break
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            dlg.setValue(min(downloaded, total))
                        QApplication.processEvents()

            # If the user pressed Cancel at any point during the loop
            if cancelled[0]:
                dlg.close()
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass
                QMessageBox.information(self, "Cancelled", "Download cancelled.")
                return

            # Successful download finished. Force 100% and close the dialog ourselves.
            if total > 0:
                dlg.setValue(total)
            dlg.close()

            # Decompress edict2.gz -> edict2 (plain text)
            plain_target = target_dir / "edict2"
            try:
                with gzip.open(target, "rb") as src, open(plain_target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "edict2",
                    f"Downloaded, but failed to decompress:\n\n{e}\n\nThe .gz file is still present."
                )
                self.jparser = JParser()
                return

            # Reload JParser so the new dictionary is picked up immediately
            self.jparser = JParser()

            QMessageBox.information(
                self,
                "edict2",
                f"Downloaded and decompressed edict2 to:\n{plain_target}\n\nJParser will use it on the next lookup."
            )

        except Exception as e:
            dlg.close()
            QMessageBox.critical(self, "Download failed", f"Could not download edict2:\n\n{e}")
