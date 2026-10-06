"""Yandex web translator: scrape a session id from the page (plain client UA first - browser UAs get a captcha wall), then post to the tr.json endpoint with Referer headers."""

from __future__ import annotations

import re
import time
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

# Browser user agents are frequently served a captcha wall on
# translate.yandex.com; the plain client UA receives the app page with the
# session id in its JSON config, so it is tried first.
_PAGE_USER_AGENTS = [
    "curl/8.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

_API_HEADERS = {
    "Origin": "https://translate.yandex.com",
    "Referer": "https://translate.yandex.com/",
}

_SESSION_INVALID = 405  # API code: sid expired or rejected


class YandexTranslator(Translator):
    name = "Yandex"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=15.0, follow_redirects=True)
        self.translate_url = "https://translate.yandex.net/api/v1/tr.json/translate"
        self.detect_url = "https://translate.yandex.net/api/v1/tr.json/detect"
        self._sid: Optional[str] = None
        self._ua: Optional[str] = None

    def _scrape_sid(self) -> Optional[str]:
        """Fetch the web app page and extract the widget session id.

        The SID ships inside the page's JSON config as "SID":"...." (older
        builds used SID: '...'), stored with its dot-separated parts
        reversed. Captcha'd responses (final URL contains "showcaptcha")
        never carry a SID.
        """
        for ua in _PAGE_USER_AGENTS:
            try:
                resp = self.client.get(
                    "https://translate.yandex.com/", headers={"User-Agent": ua}
                )
                resp.raise_for_status()
                if "showcaptcha" in str(resp.url):
                    continue
                m = re.search(r'"SID"\s*:\s*"([^"]+)"', resp.text) or re.search(
                    r"SID:\s*'([^']+)'", resp.text
                )
                if not m:
                    continue
                self._ua = ua
                return ".".join(part[::-1] for part in m.group(1).split("."))
            except Exception:
                continue
        return None

    def _get_sid(self, refresh: bool = False) -> Optional[str]:
        if refresh:
            self._sid = None
        if self._sid is None:
            self._sid = self._scrape_sid()
        return self._sid

    def _request_headers(self) -> dict:
        headers = dict(_API_HEADERS)
        if self._ua:
            headers["User-Agent"] = self._ua
        return headers

    @staticmethod
    def _request_id(sid: str) -> str:
        return f"{sid}-{int(time.time() * 1000) % 100000}-0"

    @staticmethod
    def _json(resp: httpx.Response) -> Optional[dict]:
        try:
            j = resp.json()
        except Exception:
            return None
        return j if isinstance(j, dict) else None

    def _detect_language(self, text: str) -> Optional[str]:
        sid = self._get_sid()
        if not sid:
            return None
        try:
            resp = self.client.post(
                self.detect_url,
                params={"srv": "tr-text", "id": self._request_id(sid)},
                data={"text": text},
                headers=self._request_headers(),
            )
            j = self._json(resp)
            if j and j.get("code") == 200 and j.get("lang"):
                return str(j["lang"])
        except Exception:
            pass
        return None

    def translate(
        self,
        text: str,
        src: Language | str = Language.AUTO,
        dst: Language | str = Language.English,
    ) -> TranslationResult:
        src_code = self._get_lang(src)
        dst_code = self._get_lang(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        if src_code == "auto":
            detected = self._detect_language(text)
            lang = f"{detected}-{dst_code}" if detected else dst_code
        else:
            lang = f"{src_code}-{dst_code}"

        error = "Yandex session unavailable: could not obtain a session id (captcha or blocked page). Try again later."
        for refresh in (False, True):
            sid = self._get_sid(refresh=refresh)
            if not sid:
                return TranslationResult(self.name, src_code, dst_code, "", error=error)

            resp = self.client.post(
                self.translate_url,
                params={"srv": "tr-text", "id": self._request_id(sid), "lang": lang},
                data={"text": text},
                headers=self._request_headers(),
            )

            j = self._json(resp)
            if j is None:
                # HTML/captcha came back instead of JSON; transient interstitials
                # recover with a fresh session, so retry once before failing
                body = resp.text[:120].replace("\n", " ")
                error = (
                    f"Yandex returned non-JSON (HTTP {resp.status_code}, "
                    f"{resp.headers.get('content-type', 'unknown')}): {body!r}"
                )
                continue

            if j.get("code") == 200 and isinstance(j.get("text"), list):
                return TranslationResult(
                    self.name, src_code, dst_code, "".join(j["text"]), raw=j
                )

            error = f"Yandex API error {j.get('code')}: {j.get('message', 'unknown error')}"
            if j.get("code") != _SESSION_INVALID:
                return TranslationResult(self.name, src_code, dst_code, "", error=error)
            # session rejected: loop once more with a freshly scraped sid

        return TranslationResult(self.name, src_code, dst_code, "", error=error)
