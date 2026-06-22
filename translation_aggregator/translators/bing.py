from __future__ import annotations

import re
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bing.com/translator",
    "Origin": "https://www.bing.com",
}


class BingTranslator(Translator):
    name = "Bing"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        headers = DEFAULT_HEADERS.copy()
        # Bing is very picky about cookies + headers. Keep one persistent client.
        self.client = client or httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers=headers,
        )
        self.translate_url = "https://www.bing.com/ttranslatev3"
        self.token_url = "https://www.bing.com/translator"
        self._token_data = None  # cached

    def _invalidate_token(self):
        self._token_data = None

    def _get_token(self, *, force: bool = False) -> dict:
        if self._token_data and not force:
            return self._token_data

        # Always start fresh when forced (Bing tokens are very short-lived)
        if force:
            self._token_data = None

        try:
            # 1. Always hit the translator page first so we get proper cookies (MUID, etc.)
            # This is critical — without the cookies from this page, the API returns 401.
            page_resp = self.client.get(
                self.token_url,
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
            )
            page_resp.raise_for_status()
            html = page_resp.text

            # 2. Extract IG (can be in several forms)
            ig_match = (
                re.search(r'IG:"([A-F0-9]{16,})"', html, re.I)
                or re.search(r'"IG":"([A-F0-9]{16,})"', html, re.I)
                or re.search(r'IG=([A-F0-9]{16,})', html, re.I)
                or re.search(r'"ig":"([A-F0-9]{16,})"', html, re.I)
            )

            # 3. Extract IID
            iid_match = (
                re.search(r'data-iid="([^"]+)"', html)
                or re.search(r'"IID":"([^"]+)"', html)
                or re.search(r'iid=([^"&]+)', html)
            )

            # 4. Extract the abuse prevention token + key.
            # This is the most important part for avoiding 401.
            # The original C++ looks for "var params_RichTranslateHelper"
            token = None
            key = None

            # Try the exact pattern the C++ port uses (RichTranslateHelper)
            m = re.search(
                r'params_RichTranslateHelper\s*=\s*\[(\d+),\s*"([^"]+)",\s*\d+\]',
                html,
            )
            if m:
                key = m.group(1)
                token = m.group(2)

            # Common current pattern (AbusePreventionHelper)
            if not token:
                m = re.search(
                    r'params_AbusePreventionHelper\s*=\s*\[(\d+),\s*"([^"]+)",\s*\d+\]',
                    html,
                )
                if m:
                    key = m.group(1)
                    token = m.group(2)

            # Generic [number,"longtoken",...] anywhere on the page
            if not token:
                m = re.search(r'\[(\d{9,}),\s*"([A-Za-z0-9+/=]{20,})",\s*\d+\]', html)
                if m:
                    key = m.group(1)
                    token = m.group(2)

            # Fallbacks
            if not token:
                t = re.search(r'"token"\s*:\s*"([^"]+)"', html)
                k = re.search(r'"key"\s*:\s*(\d+)', html)
                if t:
                    token = t.group(1)
                if k:
                    key = k.group(1)

            if not token:
                m = re.search(r'\[(\d{9,}),\s*"([A-Za-z0-9+/=]{25,})"', html)
                if m:
                    key = m.group(1)
                    token = m.group(2)

            ig_val = ig_match.group(1) if ig_match else ""
            iid_val = iid_match.group(1) if iid_match else "1"

            # clientId is sometimes required by Bing
            client_id = ""
            c = re.search(r'"clientId"\s*:\s*"([^"]+)"', html)
            if c:
                client_id = c.group(1)
            else:
                c = re.search(r'clientId["\s:=]+([A-Za-z0-9._-]+)', html)
                if c:
                    client_id = c.group(1)

            self._token_data = {
                "IG": ig_val,
                "IID": iid_val,
                "token": token or "",
                "key": key or "",
                "clientId": client_id,
            }
        except Exception:
            self._token_data = {"IG": "", "IID": "1", "token": "", "key": ""}
        return self._token_data

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._get_lang(src)
        dst_code = self._get_lang(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        # Bing tokens are short-lived and session-specific.
        # Always fetch fresh (force=True) to avoid stale 401s.
        tok = self._get_token(force=True)
        count = getattr(self, "_cnt", 0)
        setattr(self, "_cnt", count + 1)

        params = {
            "isVertical": "1",
            "IG": tok.get("IG", ""),
            "IID": f"translator.{tok.get('IID', '1')}.{count}",
        }

        data = {
            "text": text,
            "fromLang": src_code if src_code != "auto" else "",
            "to": dst_code,
            "token": tok.get("token", ""),
            "key": tok.get("key", ""),
        }
        if tok.get("clientId"):
            data["clientId"] = tok["clientId"]

        def _do_post(p, d):
            return self.client.post(
                self.translate_url,
                params=p,
                data=d,
                headers={
                    **DEFAULT_HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

        try:
            resp = _do_post(params, data)

            if resp.status_code == 401:
                # Token was rejected – clear everything and try once more with a brand new fetch
                self._invalidate_token()
                try:
                    self.client.cookies.clear()
                except Exception:
                    pass
                tok = self._get_token(force=True)
                params["IG"] = tok.get("IG", "")
                params["IID"] = f"translator.{tok.get('IID', '1')}.{getattr(self, '_cnt', 0)}"
                data["token"] = tok.get("token", "")
                data["key"] = tok.get("key", "")
                resp = _do_post(params, data)

            # Some 4xx/5xx still come back as 200 with error JSON; check content
            if resp.status_code != 200:
                self._invalidate_token()
                return TranslationResult(self.name, src_code, dst_code, "", error=f"HTTP {resp.status_code}")

            j = resp.json()
            out = ""
            if isinstance(j, list) and j:
                # Normal successful shape
                trans = j[0].get("translations", []) if isinstance(j[0], dict) else []
                if trans:
                    out = trans[0].get("text", "")
                # Sometimes Bing returns error object inside the first item
                if not out and isinstance(j[0], dict) and "error" in j[0]:
                    err = j[0]["error"]
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    self._invalidate_token()
                    return TranslationResult(self.name, src_code, dst_code, "", error=f"Bing: {msg}")
            elif isinstance(j, dict) and "error" in j:
                self._invalidate_token()
                return TranslationResult(self.name, src_code, dst_code, "", error=str(j["error"]))

            return TranslationResult(self.name, src_code, dst_code, out, raw=j)

        except Exception as e:
            self._invalidate_token()
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
