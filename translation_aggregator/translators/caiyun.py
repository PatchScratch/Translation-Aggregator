"""Caiyun (彩云小译, fanyi.caiyunapp.com) translator via the official API.

API: https://api.interpreter.caiyunai.com/v1/translator
Auth: X-Authorization: token <key>. Defaults to the test token published in
the docs (rate-limited, availability not guaranteed); set your own token in
the pane's settings (free tier: 1M characters/month).
"""
from __future__ import annotations

from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

API_URL = "https://api.interpreter.caiyunai.com/v1/translator"
# token published in the official docs for testing
DEFAULT_TEST_TOKEN = "3975l6lr5pcbvidl6jl2"


class CaiyunTranslator(Translator):
    name = "Caiyun"

    def __init__(self, api_key: str = "", client: Optional[httpx.Client] = None):
        super().__init__()
        self.api_key = (api_key or "").strip() or DEFAULT_TEST_TOKEN
        self.client = client or httpx.Client(timeout=20.0)

    def _lang_code(self, lang: Language | str) -> str:
        code = self._get_lang(lang)
        if code in ("zh", "zh-Hans", "zh-CN"):
            return "zh"
        if code in ("zh-TW", "zh-Hant"):
            return "zh-Hant"
        return code

    def translate(
        self,
        text: str,
        src: Language | str = Language.AUTO,
        dst: Language | str = Language.English,
    ) -> TranslationResult:
        src_code = self._lang_code(src)
        dst_code = self._lang_code(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)
        if not text.strip():
            return TranslationResult(self.name, src_code, dst_code, "")

        detect = src_code == "auto"
        source_lang = "auto" if detect else src_code
        # the API has no detect for non-Chinese targets; TA is Japanese-first
        if detect and dst_code not in ("zh", "zh-Hant"):
            source_lang = "ja"
            detect = False

        payload = {
            "source": text,
            "trans_type": f"{source_lang}2{dst_code}",
            "detect": detect,
            "media": "text",
            "request_id": "ta-port",
        }
        try:
            resp = self.client.post(
                API_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Authorization": f"token {self.api_key}",
                },
                json=payload,
            )
            j = resp.json() if resp.content else {}
            target = j.get("target")
            if resp.status_code == 200 and target:
                # string sources return a plain string, list sources a list
                if isinstance(target, list):
                    out = " ".join(str(t) for t in target if t is not None)
                else:
                    out = str(target)
                return TranslationResult(self.name, src_code, dst_code, out, raw=j)
            message = j.get("message") or str(j)[:150] or f"HTTP {resp.status_code}"
            return TranslationResult(self.name, src_code, dst_code, "", error=f"Caiyun: {message}")
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
