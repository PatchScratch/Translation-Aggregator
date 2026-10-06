"""Babelfish (babelfish.com) free web translator."""
from __future__ import annotations

import re
from html import unescape
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

HOME = "https://www.babelfish.com/"
SUCCESS_URL = "https://www.babelfish.com/success/"
MAX_CHARS = 500  # the site's textarea maxlength

_TX_OUT = re.compile(
    r'<(?:div|output|p)[^>]*class="[^"]*tx-out[^"]*"[^>]*>(.*?)</', re.S | re.I
)
_TAG = re.compile(r"<[^>]+>")


class BabelfishTranslator(Translator):
    name = "Babelfish"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=20.0, follow_redirects=True)
        self._seeded = False

    def _seed(self):
        """Visit the homepage once so the request carries normal cookies."""
        if self._seeded:
            return
        try:
            self.client.get(HOME)
        except Exception:
            pass
        self._seeded = True

    def _lang_code(self, lang: Language | str) -> str:
        code = self._get_lang(lang)
        # the site only offers Simplified Chinese
        if code.lower().startswith("zh"):
            return "zh-Hans"
        if code == "auto":
            return "ja"
        return code

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
                SUCCESS_URL,
                data={"from": src_code, "to": dst_code, "text": text[:MAX_CHARS]},
            )
            resp.raise_for_status()
            m = _TX_OUT.search(resp.text)
            if not m:
                return TranslationResult(
                    self.name, src_code, dst_code, "",
                    error="Babelfish returned no translation (page layout may have changed)",
                )
            out = unescape(_TAG.sub("", m.group(1))).strip()
            return TranslationResult(self.name, src_code, dst_code, out, raw=resp.url)
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
