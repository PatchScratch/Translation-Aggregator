from __future__ import annotations

import re
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult


class YandexTranslator(Translator):
    name = "Yandex"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=True)
        self.translate_url = "https://translate.yandex.net/api/v1/tr.json/translate"
        self._sid: Optional[str] = None

    def _get_sid(self) -> Optional[str]:
        if self._sid:
            return self._sid
        try:
            resp = self.client.get("https://translate.yandex.com/")
            resp.raise_for_status()
            m = re.search(r"SID:\s*'([^']+)'", resp.text)
            if m:
                raw = m.group(1)
                # Yandex reverses dot-separated parts
                parts = raw.split('.')
                self._sid = '.'.join(p[::-1] for p in parts)
            else:
                self._sid = None
        except Exception:
            self._sid = None
        return self._sid

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._get_lang(src)
        dst_code = self._get_lang(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        sid = self._get_sid() or ""
        params = {
            "lang": f"{src_code}-{dst_code}",
            "srv": "tr-text",
            "id": f"{sid}-{int(__import__('time').time()*1000) % 100000}-0" if sid else "",
        }

        data = {
            "from": src_code,
            "to": dst_code,
            "text": text,
        }

        try:
            resp = self.client.post(self.translate_url, params=params, data=data)
            resp.raise_for_status()
            j = resp.json()
            out = ""
            if "text" in j and isinstance(j["text"], list):
                out = "".join(j["text"])
            return TranslationResult(self.name, src_code, dst_code, out, raw=j)
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
