"""Jisho.org dictionary pane (jisho.org API v1)."""
from __future__ import annotations

from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

API_URL = "https://jisho.org/api/v1/search/words"
MAX_ENTRIES = 10


class JishoTranslator(Translator):
    name = "Jisho"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=True)

    def can_translate(self, src: Language | str, dst: Language | str) -> bool:
        return self._get_lang(src) in ("ja", "auto") and self._get_lang(dst) == "en"

    @staticmethod
    def _format_entry(entry: dict) -> str:
        japanese = entry.get("japanese") or [{}]
        main = japanese[0]
        word = main.get("word") or main.get("reading") or ""
        reading = main.get("reading") or ""
        head = f"{word} 【{reading}】" if reading and reading != word else word
        alts = [
            f"{j.get('word') or j.get('reading') or ''}" + (f" 【{j['reading']}】" if j.get("reading") and j.get("word") else "")
            for j in japanese[1:]
            if j.get("word") or j.get("reading")
        ]
        if alts:
            head += " : " + "; ".join(alts)

        tags = []
        if entry.get("is_common"):
            tags.append("(P)")
        tags.extend(entry.get("jlpt") or [])

        parts = [head]
        if tags:
            parts.append(" ".join(tags))
        senses = [
            s for s in (entry.get("senses") or [])
            # Wikipedia-title senses only carry the article name as a gloss
            if "Wikipedia definition" not in (s.get("parts_of_speech") or [])
        ]
        for i, sense in enumerate(senses, 1):
            pos = ", ".join(sense.get("parts_of_speech") or [])
            defs = "; ".join(d for d in sense.get("english_definitions") or [] if d)
            piece = f"({i}) {defs}" if defs else f"({i})"
            if pos:
                piece = f"({pos}) " + piece
            parts.append(piece)
        return " ".join(p for p in parts if p)

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
        try:
            resp = self.client.get(API_URL, params={"keyword": text})
            resp.raise_for_status()
            data = resp.json().get("data") or []
            if not data:
                return TranslationResult(self.name, src_code, dst_code, "No matches on jisho.org")
            entries = [self._format_entry(e) for e in data[:MAX_ENTRIES] if e]
            return TranslationResult(self.name, src_code, dst_code, "\n\n".join(entries), raw=data[:3])
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
