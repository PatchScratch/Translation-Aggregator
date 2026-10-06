"""Papago (papago.naver.com) web translator."""
from __future__ import annotations

from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

HOME = "https://papago.naver.com/"
API_URL = "https://papago.naver.com/api/text/translation"

# language codes the site supports (subset our language names can produce)
_LANG_CODES = {
    "ko", "en", "ja", "zh-CN", "zh-TW", "es", "fr", "vi", "th", "id",
    "de", "ru", "pt", "it", "hi",
}


class PapagoTranslator(Translator):
    name = "Papago"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                "Origin": "https://papago.naver.com",
                "Referer": "https://papago.naver.com/",
                "Accept": "application/json",
            },
        )
        self._seeded = False

    def _seed(self):
        if self._seeded:
            return
        try:
            self.client.get(HOME)
        except Exception:
            pass
        self._seeded = True

    def _lang_code(self, lang: Language | str) -> str:
        code = self._get_lang(lang)
        if code == "auto":
            # the API has no detect mode; TA is Japanese-first
            return "ja"
        if code in ("zh", "zh-Hans"):
            return "zh-CN"
        if code in ("zh-Hant",):
            return "zh-TW"
        return code

    def can_translate(self, src: Language | str, dst: Language | str) -> bool:
        return self._lang_code(src) in _LANG_CODES and self._lang_code(dst) in _LANG_CODES

    def translate(
        self,
        text: str,
        src: Language | str = Language.AUTO,
        dst: Language | str = Language.English,
    ) -> TranslationResult:
        src_code = self._lang_code(src)
        dst_code = self._lang_code(dst)

        if src_code == dst_code:
            return TranslationResult(self.name, src_code, dst_code, text)
        if not text.strip():
            return TranslationResult(self.name, src_code, dst_code, "")

        self._seed()
        try:
            resp = self.client.post(
                API_URL,
                data={
                    "source": src_code,
                    "target": dst_code,
                    "text": text,
                    "dict": "true",
                    "useGlossary": "false",
                    "honorific": "false",
                    "dictDisplay": "30",
                },
            )
            if resp.status_code != 200:
                return TranslationResult(
                    self.name, src_code, dst_code, "",
                    error=f"Papago returned HTTP {resp.status_code}",
                )
            j = resp.json()
            out = j.get("translatedText") if isinstance(j, dict) else None
            if out is None:
                return TranslationResult(
                    self.name, src_code, dst_code, "",
                    error=f"Papago returned no translation: {str(j)[:120]}",
                )
            return TranslationResult(self.name, src_code, dst_code, out, raw=j)
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
