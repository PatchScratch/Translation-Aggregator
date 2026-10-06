"""Babylon dictionary (babylon-software.com/dictionary).

The site's lookup goes through a WordPress proxy to Babylon's classic
glossary backend:

  GET <site>/wp-admin/admin-ajax.php/?action=fetch_external_data
      &url=https://info.babylon-software.com/cgi-bin/bis.fcgi
           ?rt=ol&term=<term>&tl=en&tid=iphone

(info.babylon-software.com serves an incomplete TLS chain, which is why
the proxy exists.) The response is HTML with div.term / div.definition
blocks, one per dictionary hit. This is a dictionary pane like
Jisho/WWWJDIC, not a translator: results come from whatever dictionaries
Babylon has for the term (Wikipedia, bilingual glossaries, ...).
"""
from __future__ import annotations

import re
from html import unescape
from typing import Optional
from urllib.parse import quote

import httpx

from ..base import Translator, Language, TranslationResult

HOME = "https://www.babylon-software.com/dictionary/"
PROXY = "https://www.babylon-software.com/wp-admin/admin-ajax.php/"
LOOKUP = "https://info.babylon-software.com/cgi-bin/bis.fcgi?rt=ol&term={term}&tl=en&tid=iphone"

_TERM = re.compile(r'<div[^>]*class="term[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
_DEF = re.compile(r'<div[^>]*class="definition[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
MAX_ENTRIES = 10


def _strip(fragment: str) -> str:
    text = unescape(_TAG.sub(" ", fragment))
    return re.sub(r"\s+", " ", text).strip()


class BabylonTranslator(Translator):
    name = "Babylon"

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
                "Referer": HOME,
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
        term = text.strip()
        if not term:
            return TranslationResult(self.name, src_code, dst_code, "")
        # a dictionary lookup works best on a word/short phrase
        term = term.splitlines()[0].strip()[:64]

        self._seed()
        try:
            resp = self.client.get(
                PROXY,
                params={
                    "action": "fetch_external_data",
                    "url": LOOKUP.format(term=quote(term)),
                },
            )
            resp.raise_for_status()
            html = resp.text
            terms = [_strip(t) for t in _TERM.findall(html)]
            defs_ = [_strip(d) for d in _DEF.findall(html)]
            entries = []
            for t, d in zip(terms, defs_):
                if t or d:
                    entries.append(f"{t}\n{d}" if t and t != d else (t or d))
            if not entries:
                return TranslationResult(
                    self.name, src_code, dst_code, "No matches in the Babylon dictionary"
                )
            return TranslationResult(
                self.name, src_code, dst_code, "\n\n".join(entries[:MAX_ENTRIES])
            )
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
