"""WWWJDIC word-breakdown pane. Recipe from JdicWindow.cpp."""
from __future__ import annotations

import re
from html import unescape
from typing import Optional
from urllib.parse import quote

import httpx

from ..base import Translator, Language, TranslationResult

DEFAULT_MIRROR = "https://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic"
MIRRORS = [
    "https://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic",
    "http://wwwjdic.se/cgi-bin/wwwjdic.cgi?1C",
    "http://wwwjdic.biz/cgi-bin/wwwjdic?1C",
]

_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.I)
_UL = re.compile(r"<ul>(.*?)</ul>", re.I | re.S)
_LI = re.compile(r"<li>(.*?)</li>", re.I | re.S)


def _clean_fragment(fragment: str) -> str:
    """HTML fragment -> plain text like the original TA pane.

    <br> becomes a newline; remaining tags are dropped; runs of spaces and
    tabs collapse to a single space; blank lines are dropped.
    """
    text = _BR.sub("\n", fragment)
    text = _TAG.sub("", text)
    text = unescape(text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _format_body(body: str) -> str:
    """Structure the response like JdicWindow did.

    The reply is a sequence of groups: an echoed sentence line followed by a
    <ul> whose <li> items are one dictionary entry each (long input makes the
    server emit several groups). Render each group as the sentence, a blank
    line, then one entry per paragraph separated by blank lines.
    """
    blocks: list[str] = []
    pos = 0
    for ul in _UL.finditer(body):
        sentence = _clean_fragment(body[pos:ul.start()])
        entries = [e for e in (_clean_fragment(li) for li in _LI.findall(ul.group(1))) if e]
        if entries:
            block = (sentence + "\n\n\n" if sentence else "") + "\n\n".join(entries)
        else:
            block = sentence
        if block:
            blocks.append(block)
        pos = ul.end()
    return "\n\n".join(blocks).strip()


class WwwjdicTranslator(Translator):
    name = "WWWJDIC"

    def __init__(self, mirror: str = DEFAULT_MIRROR, client: Optional[httpx.Client] = None):
        super().__init__()
        self.mirror = (mirror or DEFAULT_MIRROR).strip()
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
        # Mirrors may carry their own query (e.g. "...?1C"); the command
        # string we append replaces it, so keep only the script path.
        base = self.mirror.split("?", 1)[0].rstrip("/")
        url = f"{base}?9ZIG{quote(text, safe='')}"
        try:
            resp = self.client.get(url, headers={"User-Agent": "TranslationAggregator/0.2"})
            resp.raise_for_status()
            html = resp.text
            m = _BODY.search(html)
            body = m.group(1) if m else html
            plain = _format_body(body)
            return TranslationResult(self.name, src_code, dst_code, plain, raw=html[:2000])
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
