from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any


class Language(str, Enum):
    AUTO = "auto"
    English = "en"
    Japanese = "ja"
    Chinese_Simplified = "zh-CN"
    Chinese_Traditional = "zh-TW"
    Dutch = "nl"
    French = "fr"
    German = "de"
    Greek = "el"
    Italian = "it"
    Portuguese = "pt"
    Spanish = "es"
    Korean = "ko"
    Russian = "ru"
    Afrikaans = "af"
    Albanian = "sq"
    Arabic = "ar"
    Belarusian = "be"
    Bengali = "bn"
    Bosnian = "bs"
    Bulgarian = "bg"
    Catalan = "ca"
    Croatian = "hr"
    Czech = "cs"
    Danish = "da"
    Esperanto = "eo"
    Estonian = "et"
    Filipino = "tl"
    Finnish = "fi"
    Galician = "gl"
    Haitian_Creole = "ht"
    Hausa = "ha"
    Hebrew = "he"
    Hindi = "hi"
    Hungarian = "hu"
    Icelandic = "is"
    Indonesian = "id"
    Irish = "ga"
    Klingon = "tlh"
    Latin = "la"
    Latvian = "lv"
    Lithuanian = "lt"
    Macedonian = "mk"
    Malay = "ms"
    Maltese = "mt"
    Norwegian = "no"
    Persian = "fa"
    Polish = "pl"
    Romanian = "ro"
    Serbian = "sr"
    Slovak = "sk"
    Slovenian = "sl"
    Somali = "so"
    Swahili = "sw"
    Swedish = "sv"
    Thai = "th"
    Turkish = "tr"
    Ukrainian = "uk"
    Urdu = "ur"
    Vietnamese = "vi"
    Welsh = "cy"
    Yiddish = "yi"
    Yucatec_Maya = "yua"
    Zulu = "zu"

    # Additional for some engines
    Queretaro_Otomi = "otq"
    Hmong_Daw = "mww"


LANG_NAME_TO_CODE: Dict[str, str] = {e.name: e.value for e in Language}
CODE_TO_LANG: Dict[str, Language] = {e.value: e for e in Language}


@dataclass
class TranslationResult:
    translator: str
    src: str
    dst: str
    text: str
    raw: Optional[Any] = None
    error: Optional[str] = None


class Translator:
    name: str = "base"

    def __init__(self):
        self.session = None  # lazy

    def can_translate(self, src: Language | str, dst: Language | str) -> bool:
        return True

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        raise NotImplementedError

    def _get_lang(self, lang: Language | str, default: Language | str = Language.AUTO) -> str:
        if isinstance(lang, Language):
            return lang.value
        if lang in LANG_NAME_TO_CODE:
            return LANG_NAME_TO_CODE[lang]
        return lang or (default.value if isinstance(default, Language) else default)
