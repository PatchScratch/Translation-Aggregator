from __future__ import annotations

import json
import re
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult


def _google_escape_param(s: str) -> str:
    out = []
    for c in s:
        o = ord(c)
        if o <= 0x26 or c in ('+', ',') or (0x3A <= o <= 0x40) or c == '\\' or (0x5B <= o <= 0x60) or (0x7B <= o <= 0x7E):
            out.append(f"%{o:02X}")
        else:
            out.append(c)
    return ''.join(out)


class GoogleTranslator(Translator):
    name = "Google"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=True)
        self.host = "translate.googleapis.com"
        # Using the simpler gtx client endpoint which is more stable for scraping
        self.url = "https://translate.googleapis.com/translate_a/single"

    def _lang_code(self, lang: Language | str, src_side: bool = False) -> str:
        code = self._get_lang(lang)
        if src_side and code == "zh-TW":
            code = "zh-CN"
        if code == "auto":
            return "auto"
        return code

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._lang_code(src, src_side=True)
        dst_code = self._lang_code(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        params = {
            "client": "gtx",
            "sl": src_code,
            "tl": dst_code,
            "dt": "t",
            "ie": "UTF-8",
            "oe": "UTF-8",
            "q": text,
        }

        try:
            resp = self.client.get(self.url, params=params)
            resp.raise_for_status()
            data = resp.json()

            # data is a list; translation pieces are in data[0][i][0]
            translated_parts = []
            if isinstance(data, list) and data and isinstance(data[0], list):
                for seg in data[0]:
                    if isinstance(seg, list) and seg and seg[0]:
                        translated_parts.append(str(seg[0]))

            result_text = ''.join(translated_parts) if translated_parts else ""
            return TranslationResult(self.name, src_code, dst_code, result_text, raw=data)
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
