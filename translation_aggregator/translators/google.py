from __future__ import annotations

from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class _GoogleBlocked(Exception):
    """The free endpoint refused the request (HTTP 429 or a block page)."""


class GoogleTranslator(Translator):
    name = "Google Translate"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=True)
        self.host = "translate.googleapis.com"
        # Canonical free endpoint (richer response, but aggressively
        # rate-limited per IP).
        self.url = "https://translate.googleapis.com/translate_a/single"
        # Endpoint the Chrome extensions use; same service, separate
        # rate-limit bucket, answers even when gtx is 429ing.
        self.fallback_url = "https://clients5.google.com/translate_a/t"
        self._headers = {"User-Agent": _BROWSER_UA}
        # Once gtx has rate-limited us, try the fallback first; resets only
        # if the fallback starts failing too.
        self._prefer_fallback = False

    def _lang_code(self, lang: Language | str, src_side: bool = False) -> str:
        code = self._get_lang(lang)
        if src_side and code == "zh-TW":
            code = "zh-CN"
        if code == "auto":
            return "auto"
        return code

    def translate(
        self,
        text: str,
        src: Language | str = Language.AUTO,
        dst: Language | str = Language.English,
    ) -> TranslationResult:
        src_code = self._lang_code(src, src_side=True)
        dst_code = self._lang_code(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        attempts = (
            [self._via_clients5, self._via_gtx] if self._prefer_fallback
            else [self._via_gtx, self._via_clients5]
        )
        error: Optional[str] = None
        for attempt in attempts:
            try:
                return attempt(text, src_code, dst_code)
            except _GoogleBlocked as e:
                error = str(e)
                self._prefer_fallback = not self._prefer_fallback
            except Exception as e:
                return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
        return TranslationResult(self.name, src_code, dst_code, "", error=error)

    # -- endpoint: translate.googleapis.com/translate_a/single?client=gtx ----

    def _via_gtx(self, text: str, src_code: str, dst_code: str) -> TranslationResult:
        params = {
            "client": "gtx",
            "sl": src_code,
            "tl": dst_code,
            "dt": "t",
            "ie": "UTF-8",
            "oe": "UTF-8",
            "q": text,
        }
        resp = self.client.get(self.url, params=params, headers=self._headers)
        if resp.status_code == 429:
            raise _GoogleBlocked(
                "Google Translate endpoint rate-limited (HTTP 429): "
                f"{self.url}"
            )
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

    # -- endpoint: clients5.google.com/translate_a/t?client=dict-chrome-ex ---

    def _via_clients5(self, text: str, src_code: str, dst_code: str) -> TranslationResult:
        params = {
            "client": "dict-chrome-ex",
            "sl": src_code,
            "tl": dst_code,
            "q": text,
        }
        resp = self.client.post(self.fallback_url, params=params, headers=self._headers)
        if resp.status_code == 429:
            raise _GoogleBlocked(
                "Google Translate endpoint rate-limited (HTTP 429): "
                f"{self.fallback_url}"
            )
        resp.raise_for_status()
        data = resp.json()

        # Response shapes:
        #   ["translated", ...]                       - source language given
        #   [["translated", "ja"], ...]               - sl=auto, lang detected
        result_text = ""
        if isinstance(data, list) and data:
            if isinstance(data[0], list):
                result_text = ''.join(
                    str(seg[0]) for seg in data
                    if isinstance(seg, list) and seg and seg[0]
                )
            else:
                result_text = ''.join(s for s in data if isinstance(s, str))

        return TranslationResult(self.name, src_code, dst_code, result_text, raw=data)
