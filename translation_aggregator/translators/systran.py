"""Systran (systransoft.com/translate) via the free widget's API.

The page's widget posts to the official Systran API using client
credentials embedded in the page (translate.systran.net/oidc/token ->
api-translate.systran.net). Auto-detection: leave "source" empty and the
response reports the detected language per document.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

TOKEN_URL = "https://translate.systran.net/oidc/token"
API_URL = "https://api-translate.systran.net/translation/text/translate"
CLIENT_ID = "RRW2CEVhhJLeuDz5qEy4s"
CLIENT_SECRET = "az7bL-8taK38fyQMvmdJVxa9AIsW5w6uG-qn1bI0tpkt2IrppXaUYF7tKLz6NOnz5eqIWMvrkr4V700D1lNECg"


class SystranTranslator(Translator):
    name = "Systran"

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
                "Referer": "https://www.systransoft.com/",
            },
        )
        self._token: str = ""
        self._token_at = 0.0

    def _get_token(self, force: bool = False) -> str:
        if not force and self._token and time.time() - self._token_at < 3000:
            return self._token
        r = self.client.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        self._token = r.json().get("access_token", "")
        self._token_at = time.time()
        return self._token

    def _lang_code(self, lang: Language | str) -> str:
        code = self._get_lang(lang)
        if code in ("zh", "zh-Hans", "zh-CN"):
            return "zh-CN"
        if code in ("zh-TW", "zh-Hant"):
            return "zh-TW"
        return code

    @staticmethod
    def _extract(j: dict) -> str:
        outputs = j.get("outputs") or []
        pieces = []
        for out in outputs:
            doc = (out.get("output") or {}).get("documents") or [{}] if isinstance(out.get("output"), dict) else []
            for d in doc:
                for unit in d.get("trans_units") or []:
                    for sent in unit.get("sentences") or []:
                        alts = sent.get("alt_transes") or []
                        if alts:
                            pieces.append((alts[0].get("target") or {}).get("text", ""))
                        else:
                            pieces.append((sent.get("target") or {}).get("text", ""))
        return " ".join(p for p in pieces if p)

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

        params = {
            "source": "" if src_code == "auto" else src_code,
            "target": dst_code,
            "autodetectionMode": "single",
            "withInfo": "true",
            "format": "text/plain",
            "withAnnotations": "true",
        }
        for attempt in (False, True):
            token = self._get_token(force=attempt)
            if not token:
                return TranslationResult(
                    self.name, src_code, dst_code, "",
                    error="Systran: could not obtain an access token",
                )
            resp = self.client.post(
                API_URL, params=params, json={"inputs": [text]},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401 or resp.status_code == 403:
                continue  # expired token -> one refresh
            try:
                j = resp.json()
            except Exception:
                return TranslationResult(
                    self.name, src_code, dst_code, "",
                    error=f"Systran returned non-JSON (HTTP {resp.status_code})",
                )
            out = self._extract(j)
            if out:
                return TranslationResult(self.name, src_code, dst_code, out, raw=j)
            return TranslationResult(
                self.name, src_code, dst_code, "",
                error=f"Systran returned no translation: {str(j)[:120]}",
            )
        return TranslationResult(
            self.name, src_code, dst_code, "",
            error="Systran rejected the request (unauthorized)",
        )
