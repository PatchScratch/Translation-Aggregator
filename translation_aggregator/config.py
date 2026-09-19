from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Any

import platformdirs


APP_NAME = "TranslationAggregator"
APP_AUTHOR = "TA-Python-Port"


def _config_dir() -> Path:
    return Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))


def _default_config_path() -> Path:
    local = Path("TranslationAggregator.ini")
    if local.exists():
        return local
    return _config_dir() / "config.json"


@dataclass
class AppConfig:
    lang_src: str = "ja"
    lang_dst: str = "en"

    auto_clipboard: bool = True
    enable_substitutions: bool = True
    auto_hiragana: bool = False
    half_to_full: bool = False

    jparser_use_mecab: bool = True
    jparser_show_conj: bool = True
    jparser_japanese_own_line: bool = False
    jparser_hide_pos: bool = False
    jparser_hide_usage: bool = False
    jparser_hide_crossrefs: bool = True
    jparser_definition_lines: bool = False
    jparser_reformat_numbers: bool = False
    jparser_no_kana_brackets: bool = False
    jparser_furigana: str = "none"
    jparser_font_size_normal: int = 11
    jparser_font_size_furigana: int = 8
    jparser_color_default: str = "000000"
    jparser_color_translated: str = "C8F0C8"
    jparser_color_particles: str = "E0E0FF"
    jparser_color_furigana: str = "000000"
    jparser_color_kanji: str = "A00000"
    jparser_color_kana: str = "1EA01E"
    jparser_color_parentheses: str = "64AAE6"
    jparser_color_conjugations: str = "969696"

    mecab_furigana: str = "hiragana"
    mecab_font_size_normal: int = 13
    mecab_font_size_furigana: int = 10
    mecab_color_default: str = "80F9FF"
    mecab_color_furigana: str = "E0DE00"
    mecab_color_particles: str = "E0DEFF"

    atlas_environment: str = "General"
    atlas_trs_path: str = ""
    atlas_flags: int = 0

    enabled_translators: List[str] = field(
        default_factory=lambda: ["google", "bing", "deepl", "yandex", "wwwjdic"]
    )

    deepl_mode: str = "free"
    deepl_api_key: str = ""
    deepl_api_base_url: str = ""

    wwwjdic_mirror: str = "https://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic"

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_system_prompt: str = (
        "Translate the user text from {src} to {dst}. "
        "Return only the translation. Preserve line breaks."
    )

    dictionaries_dir: str = "dictionaries"
    mecab_path: str = ""

    substitutions: Dict[str, List[List[str]]] = field(default_factory=dict)
    geometry: Dict[str, Any] = field(default_factory=dict)

    path: Path = field(default_factory=_default_config_path, repr=False)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("path", None)
        if self.path.suffix.lower() == ".json":
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
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
