from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QDialogButtonBox, QLabel, QLineEdit, QPushButton, QColorDialog
)


class MecabConfigDialog(QDialog):
    """Mecab Configuration dialog matching the original TA Mecab Configuration UI."""

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle("Mecab Configuration")
        self.cfg = cfg
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # Top row: Characters + Font sizes side by side
        top = QHBoxLayout()

        # Characters
        g_char = QGroupBox("Characters")
        l_char = QVBoxLayout(g_char)
        self.rb_hira = QRadioButton("Hiragana")
        self.rb_kata = QRadioButton("Katakana")
        self.rb_roma = QRadioButton("Romaji")

        mode = (getattr(self.cfg, "mecab_furigana", "hiragana") or "hiragana").lower()
        if mode == "katakana":
            self.rb_kata.setChecked(True)
        elif mode == "romaji":
            self.rb_roma.setChecked(True)
        else:
            self.rb_hira.setChecked(True)

        l_char.addWidget(self.rb_hira)
        l_char.addWidget(self.rb_kata)
        l_char.addWidget(self.rb_roma)
        top.addWidget(g_char)

        # Font sizes
        g_font = QGroupBox("Font sizes")
        l_font = QVBoxLayout(g_font)

        row_n = QHBoxLayout()
        row_n.addWidget(QLabel("Normal"))
        self.font_normal = QLineEdit(str(getattr(self.cfg, "mecab_font_size_normal", 13)))
        self.font_normal.setFixedWidth(60)
        row_n.addWidget(self.font_normal)
        l_font.addLayout(row_n)

        row_f = QHBoxLayout()
        row_f.addWidget(QLabel("Furigana"))
        self.font_furi = QLineEdit(str(getattr(self.cfg, "mecab_font_size_furigana", 10)))
        self.font_furi.setFixedWidth(60)
        row_f.addWidget(self.font_furi)
        l_font.addLayout(row_f)

        top.addWidget(g_font)
        layout.addLayout(top)

        # Word highlight colors
        g_colors = QGroupBox("Word highlight colors")
        l_colors = QVBoxLayout(g_colors)

        def _add_color_row(label: str, value: str, attr_name: str):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            ed = QLineEdit(str(value or "000000"))
            ed.setFixedWidth(70)
            ed.setAlignment(Qt.AlignmentFlag.AlignRight)
            setattr(self, attr_name, ed)
            row.addWidget(ed)
            btn = QPushButton("...")
            btn.setFixedWidth(22)
            btn.clicked.connect(lambda _=False, e=ed: self._pick_color(e))
            row.addWidget(btn)
            l_colors.addLayout(row)

        _add_color_row("Default:", getattr(self.cfg, "mecab_color_default", "80F9FF"), "color_default")
        _add_color_row("Words with furigana:", getattr(self.cfg, "mecab_color_furigana", "E0DE00"), "color_furigana")
        _add_color_row("Particles:", getattr(self.cfg, "mecab_color_particles", "E0DEFF"), "color_particles")

        layout.addWidget(g_colors)

        # Buttons: OK, Cancel, Apply
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        apply_btn = bb.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self._apply)
        layout.addWidget(bb)

    def _pick_color(self, edit: QLineEdit):
        cur = (edit.text() or "000000").strip()
        if len(cur) == 6:
            r, g, b = int(cur[0:2], 16), int(cur[2:4], 16), int(cur[4:6], 16)
            init = QColor(r, g, b)
        else:
            init = QColor(0, 0, 0)
        col = QColorDialog.getColor(init, self, "Select Color")
        if col.isValid():
            edit.setText(f"{col.red():02X}{col.green():02X}{col.blue():02X}")

    def _clean_color(self, s: str) -> str:
        s = (s or "").strip().upper().replace("#", "")
        if len(s) != 6:
            return "000000"
        return s

    def _save_to_cfg(self):
        if self.rb_hira.isChecked():
            self.cfg.mecab_furigana = "hiragana"
        elif self.rb_kata.isChecked():
            self.cfg.mecab_furigana = "katakana"
        else:
            self.cfg.mecab_furigana = "romaji"

        try:
            self.cfg.mecab_font_size_normal = int(self.font_normal.text().strip() or "13")
        except Exception:
            self.cfg.mecab_font_size_normal = 13

        try:
            self.cfg.mecab_font_size_furigana = int(self.font_furi.text().strip() or "10")
        except Exception:
            self.cfg.mecab_font_size_furigana = 10

        self.cfg.mecab_color_default = self._clean_color(self.color_default.text())
        self.cfg.mecab_color_furigana = self._clean_color(self.color_furigana.text())
        self.cfg.mecab_color_particles = self._clean_color(self.color_particles.text())

    def _apply(self):
        self._save_to_cfg()
        self.cfg.save()
        # Refresh MeCab pane live if possible
        parent = self.parent()
        if parent and hasattr(parent, "_refresh_mecab_from_source"):
            try:
                parent._refresh_mecab_from_source()
            except Exception:
                pass

    def accept(self):
        self._save_to_cfg()
        self.cfg.save()
        super().accept()
