"""WWWJDIC word-breakdown pane. Recipe from JdicWindow.cpp."""
from __future__ import annotations

import re
from html import unescape
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

DEFAULT_MIRROR = "https://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic"
MIRRORS = [
    "https://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic",
    "http://wwwjdic.se/cgi-bin/wwwjdic.cgi",
    "http://wwwjdic.biz/cgi-bin/wwwjdic",
    "https://gengo.com/wwwjdic/cgi-data/wwwjdic",
]

_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


class WwwjdicTranslator(Translator):
    name = "WWWJDIC"

    def __init__(self, mirror: str = DEFAULT_MIRROR, client: Optional[httpx.Client] = None):
        super().__init__()
        self.mirror = mirror.rstrip("?/")
        self.client = client or httpx.Client(timeout=20.0, follow_redirects=True)

    def can_translate(self, src: Language | str, dst: Language | str) -> bool:
        return self._get_lang(src) in ("ja", "auto") and self._get_lang(dst) == "en"

    def translate(
        self,
        text: str,
        src: Language | str = Language.Japanese,
        dst: Language | str = Language.English,
    ) -> TranslationResult:
        src_code = self._get_lang(src, Language.Japanese)
        dst_code = self._get_lang(dst, Language.English)
        if not text.strip():
            return TranslationResult(self.name, src_code, dst_code, "")
        url = f"{self.mirror}?9ZIG{text}"
        try:
            resp = self.client.get(url, headers={"User-Agent": "TranslationAggregator/0.2"})
            resp.raise_for_status()
            html = resp.text
            m = _BODY.search(html)
            body = m.group(1) if m else html
            plain = unescape(_TAG.sub("", body))
            plain = re.sub(r"\n{3,}", "\n\n", plain).strip()
            return TranslationResult(self.name, src_code, dst_code, plain, raw=html[:2000])
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
