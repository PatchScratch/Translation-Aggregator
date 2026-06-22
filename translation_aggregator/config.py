from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Any

import platformdirs


APP_NAME = "TranslationAggregator"
APP_AUTHOR = "TA-Python-Port"


def _config_dir() -> Path:
    return Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))


def _default_config_path() -> Path:
    # Keep similar to original: prefer local ini next to exe / cwd for familiarity
    local = Path("TranslationAggregator.ini")
    if local.exists():
        return local
    return _config_dir() / "config.json"


@dataclass
class AppConfig:
    # Language selection (use Language enum values or names)
    lang_src: str = "ja"
    lang_dst: str = "en"

    # General
    auto_clipboard: bool = True
    enable_substitutions: bool = True
    auto_hiragana: bool = False
    half_to_full: bool = False

    # JParser flags (mirrors JPARSER_*)
    jparser_use_mecab: bool = True
    jparser_show_conj: bool = True
    jparser_japanese_own_line: bool = False
    jparser_hide_pos: bool = False
    jparser_hide_usage: bool = False
    jparser_hide_crossrefs: bool = True
    jparser_definition_lines: bool = False
    jparser_reformat_numbers: bool = False
    jparser_no_kana_brackets: bool = False

    # JParser furigana mode for the GUI pane
    # none | hiragana | katakana | romaji
    jparser_furigana: str = "none"

    # JParser font sizes (points)
    jparser_font_size_normal: int = 11
    jparser_font_size_furigana: int = 8

    # JParser word highlight colors (6 hex digits RRGGBB, no #)
    jparser_color_default: str = "000000"
    jparser_color_translated: str = "C8F0C8"
    jparser_color_particles: str = "E0E0FF"
    jparser_color_furigana: str = "000000"

    # JParser tooltip colors (6 hex digits RRGGBB, no #)
    jparser_color_kanji: str = "A00000"
    jparser_color_kana: str = "1EA01E"
    jparser_color_parentheses: str = "64AAE6"
    jparser_color_conjugations: str = "969696"

    # MeCab pane furigana mode (none | hiragana | katakana | romaji)
    # Default matches original TA MeCab pane (HIRAGANA)
    mecab_furigana: str = "hiragana"

    # MeCab font sizes (points) - match original Mecab Configuration dialog
    mecab_font_size_normal: int = 13
    mecab_font_size_furigana: int = 10

    # MeCab word highlight colors (6 hex digits RRGGBB, no #)
    mecab_color_default: str = "80F9FF"
    mecab_color_furigana: str = "E0DE00"   # "Words with furigana"
    mecab_color_particles: str = "E0DEFF"

    # ATLAS config (mirrors AtlasConfig + dialog in original)
    atlas_environment: str = "General"
    atlas_trs_path: str = ""          # rule set file name (without path) or empty
    atlas_flags: int = 0              # bitmask: matches IDC_ELLIPSES etc. in AtlasDialogProc

    # Translators enabled
    enabled_translators: List[str] = field(default_factory=lambda: ["google", "bing", "deepl"])

    # DeepL settings
    # mode: "free" (scraped web endpoint) or "api" (official DeepL API)
    deepl_mode: str = "free"          # "free" or "api"
    deepl_api_key: str = ""           # required when deepl_mode == "api"
    deepl_api_base_url: str = ""      # optional override (e.g. https://api-free.deepl.com/v2/translate)

    # Paths
    dictionaries_dir: str = "dictionaries"
    mecab_path: str = ""  # optional explicit path to mecab or libmecab

    # Substitutions (profile -> list of (old, rep))
    substitutions: Dict[str, List[List[str]]] = field(default_factory=dict)

    # Window geometry (serialized)
    geometry: Dict[str, Any] = field(default_factory=dict)

    path: Path = field(default_factory=_default_config_path, repr=False)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # don't persist path itself
        data.pop("path", None)
        if self.path.suffix.lower() == ".json":
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
            # very simple ini-like for familiarity (only top level scalars + json blob for complex)
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{k}={json.dumps(v)}")
                else:
                    lines.append(f"{k}={v}")
            self.path.write_text("\n".join(lines), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        p = path or _default_config_path()
        cfg = cls(path=p)
        if not p.exists():
            return cfg
        try:
            if p.suffix.lower() == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))
            else:
                data = {}
                for line in p.read_text(encoding="utf-8").splitlines():
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    try:
                        data[k] = json.loads(v)
                    except Exception:
                        data[k] = v
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        except Exception:
            pass
        return cfg


config = AppConfig.load()
