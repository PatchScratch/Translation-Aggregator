from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QDialogButtonBox, QLabel, QLineEdit, QCheckBox, QPushButton, QColorDialog
)

from ..config import AppConfig


class JParserConfigDialog(QDialog):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.setWindowTitle("JParser Settings")
        self.cfg = cfg
        self._mode = (cfg.jparser_furigana or "none").lower()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        g = QGroupBox("Furigana")
        l = QVBoxLayout(g)

        self.rb_none = QRadioButton("None")
        self.rb_hira = QRadioButton("Hiragana")
        self.rb_kata = QRadioButton("Katakana")
        self.rb_roma = QRadioButton("Romaji")

        if self._mode == "hiragana":
            self.rb_hira.setChecked(True)
        elif self._mode == "katakana":
            self.rb_kata.setChecked(True)
        elif self._mode == "romaji":
            self.rb_roma.setChecked(True)
        else:
            self.rb_none.setChecked(True)

        l.addWidget(self.rb_none)
        l.addWidget(self.rb_hira)
        l.addWidget(self.rb_kata)
        l.addWidget(self.rb_roma)

        # Font Sizes
        g_font = QGroupBox("Font Sizes")
        l_font = QVBoxLayout(g_font)

        row_n = QHBoxLayout()
        row_n.addWidget(QLabel("Normal:"))
        self.font_normal = QLineEdit(str(getattr(self.cfg, "jparser_font_size_normal", 11)))
        self.font_normal.setFixedWidth(60)
        self.font_normal.setAlignment(Qt.AlignmentFlag.AlignRight)
        row_n.addWidget(self.font_normal)
        row_n.addStretch(1)
        l_font.addLayout(row_n)

        row_f = QHBoxLayout()
        row_f.addWidget(QLabel("Furigana:"))
        self.font_furigana = QLineEdit(str(getattr(self.cfg, "jparser_font_size_furigana", 8)))
        self.font_furigana.setFixedWidth(60)
        self.font_furigana.setAlignment(Qt.AlignmentFlag.AlignRight)
        row_f.addWidget(self.font_furigana)
        row_f.addStretch(1)
        l_font.addLayout(row_f)

        # Definition display
        g_def = QGroupBox("Definition display")
        l_def = QVBoxLayout(g_def)

        self.cb_show_conj = QCheckBox("Verb conjugations")
        self.cb_show_conj.setChecked(getattr(self.cfg, "jparser_show_conj", True))

        self.cb_jap_own_line = QCheckBox("Japanese of own line")
        self.cb_jap_own_line.setChecked(getattr(self.cfg, "jparser_japanese_own_line", False))

        self.cb_def_lines = QCheckBox("Each definition on own line")
        self.cb_def_lines.setChecked(getattr(self.cfg, "jparser_definition_lines", False))

        self.cb_reformat = QCheckBox("Reformat numbers")
        self.cb_reformat.setChecked(getattr(self.cfg, "jparser_reformat_numbers", False))

        self.cb_no_brackets = QCheckBox("No brackets arond kana")
        self.cb_no_brackets.setChecked(getattr(self.cfg, "jparser_no_kana_brackets", False))

        l_def.addWidget(self.cb_show_conj)
        l_def.addWidget(self.cb_jap_own_line)
        l_def.addWidget(self.cb_def_lines)
        l_def.addWidget(self.cb_reformat)
        l_def.addWidget(self.cb_no_brackets)

        # Horizontal row: Furigana | Font Sizes | Definition display
        top_row = QHBoxLayout()
        top_row.addWidget(g)
        top_row.addWidget(g_font)
        top_row.addWidget(g_def)
        layout.addLayout(top_row)

        # Hide text (below the three boxes)
        g_hide = QGroupBox("Hide text")
        l_hide = QHBoxLayout(g_hide)

        self.cb_hide_crossrefs = QCheckBox("Hide cross references")
        self.cb_hide_crossrefs.setChecked(getattr(self.cfg, "jparser_hide_crossrefs", True))

        self.cb_hide_usage = QCheckBox("Hide usage hints")
        self.cb_hide_usage.setChecked(getattr(self.cfg, "jparser_hide_usage", False))

        self.cb_hide_pos = QCheckBox("Hide parts of speech")
        self.cb_hide_pos.setChecked(getattr(self.cfg, "jparser_hide_pos", False))

        l_hide.addWidget(self.cb_hide_crossrefs)
        l_hide.addWidget(self.cb_hide_usage)
        l_hide.addWidget(self.cb_hide_pos)
        layout.addWidget(g_hide)

        # JParser engine option (moved from main Settings)
        self.cb_use_mecab = QCheckBox("Use MeCab (if available)")
        self.cb_use_mecab.setChecked(getattr(self.cfg, "jparser_use_mecab", True))
        layout.addWidget(self.cb_use_mecab)

        # Word Highlight Colors - bottom, right side
        g_colors = QGroupBox("Word Highlight Colors")
        l_colors = QVBoxLayout(g_colors)

        def _add_color_row(text: str, value: str, attr: str, target: QVBoxLayout):
            row = QHBoxLayout()
            row.addWidget(QLabel(text))
            ed = QLineEdit(str(value or "000000"))
            ed.setFixedWidth(70)
            ed.setAlignment(Qt.AlignmentFlag.AlignRight)
            setattr(self, attr, ed)
            row.addWidget(ed)
            btn = QPushButton("...")
            btn.setFixedWidth(22)
            btn.clicked.connect(lambda _=False, e=ed: self._pick_color(e))
            row.addWidget(btn)
            target.addLayout(row)

        _add_color_row("Default:", getattr(self.cfg, "jparser_color_default", "000000"), "color_default", l_colors)
        _add_color_row("Translated words:", getattr(self.cfg, "jparser_color_translated", "C8F0C8"), "color_translated", l_colors)
        _add_color_row("Particles:", getattr(self.cfg, "jparser_color_particles", "E0E0FF"), "color_particles", l_colors)
        _add_color_row("Words with furigana:", getattr(self.cfg, "jparser_color_furigana", "000000"), "color_furigana", l_colors)

        # Tooltip Colors - beside Word Highlight Colors
        g_tooltip = QGroupBox("Tooltip Colors")
        l_tooltip = QVBoxLayout(g_tooltip)

        _add_color_row("Kanji:", getattr(self.cfg, "jparser_color_kanji", "A00000"), "color_kanji", l_tooltip)
        _add_color_row("Kana:", getattr(self.cfg, "jparser_color_kana", "1EA01E"), "color_kana", l_tooltip)
        _add_color_row("Parentheses:", getattr(self.cfg, "jparser_color_parentheses", "64AAE6"), "color_parentheses", l_tooltip)
        _add_color_row("Conjugations:", getattr(self.cfg, "jparser_color_conjugations", "969696"), "color_conjugations", l_tooltip)

        lower = QHBoxLayout()
        lower.addStretch(1)
        lower.addWidget(g_colors)
        lower.addWidget(g_tooltip)
        layout.addLayout(lower)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def accept(self):
        if self.rb_hira.isChecked():
            self.cfg.jparser_furigana = "hiragana"
        elif self.rb_kata.isChecked():
            self.cfg.jparser_furigana = "katakana"
        elif self.rb_roma.isChecked():
            self.cfg.jparser_furigana = "romaji"
        else:
            self.cfg.jparser_furigana = "none"

        try:
            self.cfg.jparser_font_size_normal = int(self.font_normal.text().strip() or "11")
        except Exception:
            self.cfg.jparser_font_size_normal = 11

        try:
            self.cfg.jparser_font_size_furigana = int(self.font_furigana.text().strip() or "8")
        except Exception:
            self.cfg.jparser_font_size_furigana = 8

        self.cfg.jparser_show_conj = self.cb_show_conj.isChecked()
        self.cfg.jparser_japanese_own_line = self.cb_jap_own_line.isChecked()
        self.cfg.jparser_definition_lines = self.cb_def_lines.isChecked()
        self.cfg.jparser_reformat_numbers = self.cb_reformat.isChecked()
        self.cfg.jparser_no_kana_brackets = self.cb_no_brackets.isChecked()

        self.cfg.jparser_hide_crossrefs = self.cb_hide_crossrefs.isChecked()
        self.cfg.jparser_hide_usage = self.cb_hide_usage.isChecked()
        self.cfg.jparser_hide_pos = self.cb_hide_pos.isChecked()

        self.cfg.jparser_use_mecab = self.cb_use_mecab.isChecked()

        self.cfg.jparser_color_default = self._clean_color(self.color_default.text())
        self.cfg.jparser_color_translated = self._clean_color(self.color_translated.text())
        self.cfg.jparser_color_particles = self._clean_color(self.color_particles.text())
        self.cfg.jparser_color_furigana = self._clean_color(self.color_furigana.text())

        self.cfg.jparser_color_kanji = self._clean_color(self.color_kanji.text())
        self.cfg.jparser_color_kana = self._clean_color(self.color_kana.text())
        self.cfg.jparser_color_parentheses = self._clean_color(self.color_parentheses.text())
        self.cfg.jparser_color_conjugations = self._clean_color(self.color_conjugations.text())

        super().accept()

    def _pick_color(self, edit: QLineEdit):
        cur = (edit.text() or "000000").strip()
        if len(cur) == 6:
            r, g, b = int(cur[0:2], 16), int(cur[2:4], 16), int(cur[4:6], 16)
            init = QColor(r, g, b)
        else:
            init = QColor(0, 0, 0)
        col = QColorDialog.getColor(init, self, "Select color")
        if col.isValid():
            hex6 = f"{col.red():02X}{col.green():02X}{col.blue():02X}"
            edit.setText(hex6)

    def _clean_color(self, s: str) -> str:
        s = (s or "").strip().upper()
        if len(s) > 6:
            s = s[-6:]
        if len(s) < 6:
            s = ("0" * (6 - len(s))) + s
        return s if all(c in "0123456789ABCDEF" for c in s) else "000000"
