from __future__ import annotations

import json
import time
import random
import threading
from typing import Optional, List

import httpx

from ..base import Translator, Language, TranslationResult
from ..config import config


DEEPL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.deepl.com/translator",
    "Origin": "https://www.deepl.com",
    "Content-Type": "application/json",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


SPLIT_SEQUENCES = [
    b"\n", b".", b"!", b"?", b";", b'"', b":",
    b"\xef\xbc\x9f", b"\xe3\x80\x82", b"\xef\xbc\x8e", b"\xef\xbc\x81",
]


def _split_for_deepl(s: str) -> List[str]:
    splits = []
    i = 0
    start = 0
    n = len(s)
    while i < n:
        matched = False
        for seq in SPLIT_SEQUENCES:
            if i + len(seq) <= n and s[i:i+len(seq)].encode("utf-8") == seq:
                part = s[start:i + len(seq)]
                splits.append(part)
                start = i + len(seq)
                i = start
                matched = True
                break
        if not matched:
            i += 1
    if start < n:
        splits.append(s[start:])
    return [p for p in splits if p.strip()]


# =============================================================================
# FREE (scraped) implementation - very defensive against 429s
# =============================================================================

_DEEPL_CLIENT: Optional[httpx.Client] = None
_DEEPL_LOCK = threading.Lock()

DEEPL_FREE_URL = "https://www2.deepl.com/jsonrpc"


class DeepLFreeTranslator(Translator):
    """Unofficial scraping of DeepL free web interface.
    This is fragile and frequently rate-limited (429).
    """
    name = "DeepL (free)"

    _last_call_ts: float = 0.0
    _consecutive_429s: int = 0
    _blocked_until: float = 0.0

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        global _DEEPL_CLIENT
        if client is not None:
            self.client = client
        else:
            with _DEEPL_LOCK:
                if _DEEPL_CLIENT is None:
                    _DEEPL_CLIENT = httpx.Client(
                        timeout=25.0,
                        follow_redirects=True,
                        headers=DEEPL_HEADERS,
                    )
                self.client = _DEEPL_CLIENT

        self.url = DEEPL_FREE_URL
        self._id = random.randint(100000, 999999) * 10000
        self._warmed_up = False

    def _warm_up(self):
        if self._warmed_up:
            return
        try:
            self.client.get("https://www.deepl.com/", headers=DEEPL_HEADERS, timeout=10)
            time.sleep(random.uniform(0.6, 1.2))
            self.client.get("https://www.deepl.com/translator", headers=DEEPL_HEADERS, timeout=12)
            time.sleep(random.uniform(0.8, 1.5))
            self.client.get("https://www2.deepl.com/", headers=DEEPL_HEADERS, timeout=8)
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass
        self._warmed_up = True

    def _respect_rate_limit(self) -> bool:
        with _DEEPL_LOCK:
            now = time.time()
            if now < DeepLFreeTranslator._blocked_until:
                return False
            base_gap = 10.0 + (DeepLFreeTranslator._consecutive_429s * 5.0)
            gap = base_gap + random.uniform(2.5, 6.0)
            elapsed = now - DeepLFreeTranslator._last_call_ts
            if elapsed < gap:
                time.sleep(gap - elapsed)
            DeepLFreeTranslator._last_call_ts = time.time()
            return True

    def _lang_code(self, lang: Language | str, is_src: bool = False) -> str:
        code = self._get_lang(lang).upper()
        if is_src and code == "ZH-TW":
            code = "ZH"
        return "AUTO" if code == "AUTO" else code

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._lang_code(src, is_src=True)
        dst_code = self._lang_code(dst)

        if src_code == dst_code and src_code != "AUTO":
            return TranslationResult(self.name, src_code, dst_code, text)

        self._warm_up()
        if not self._respect_rate_limit():
            return TranslationResult(
                self.name, src_code, dst_code, "",
                error="DeepL (free) temporarily blocked due to rate limits."
            )

        jobs = []
        parts = _split_for_deepl(text) or [text]
        for i, part in enumerate(parts):
            if not part.strip():
                continue
            jobs.append({
                "kind": "default",
                "sentences": [{"text": part, "id": i, "prefix": ""}],
                "raw_en_context_before": [],
                "raw_en_context_after": [],
                "preferred_num_beams": 1,
            })

        ts = int(time.time() * 1000)
        self._id += 1
        payload = {
            "id": self._id,
            "jsonrpc": "2.0",
            "method": "LMT_handle_jobs",
            "params": {
                "jobs": jobs,
                "lang": {
                    "source_lang_computed": src_code,
                    "target_lang": dst_code,
                },
                "priority": 1,
                "commonJobParams": {"mode": "translate", "browserType": 1},
                "timestamp": ts,
            },
        }

        try:
            body = json.dumps(payload).replace('"LMT_handle_jobs"', ' "LMT_handle_jobs"')
            resp = self.client.post(self.url, content=body.encode("utf-8"), headers=DEEPL_HEADERS)

            if resp.status_code == 429:
                with _DEEPL_LOCK:
                    DeepLFreeTranslator._consecutive_429s = min(DeepLFreeTranslator._consecutive_429s + 1, 10)
                    DeepLFreeTranslator._blocked_until = time.time() + (50 + DeepLFreeTranslator._consecutive_429s * 10)
                return TranslationResult(self.name, src_code, dst_code, "", error="DeepL (free) rate limit (429)")

            resp.raise_for_status()
            j = resp.json()

            with _DEEPL_LOCK:
                if DeepLFreeTranslator._consecutive_429s > 0:
                    DeepLFreeTranslator._consecutive_429s -= 1

            out_parts = []
            if isinstance(j, dict) and "result" in j:
                for tr in j["result"].get("translations", []):
                    for beam in tr.get("beams", []):
                        for sent in beam.get("sentences", []):
                            if "text" in sent:
                                out_parts.append(sent["text"])
            return TranslationResult(self.name, src_code, dst_code, "".join(out_parts), raw=j)

        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 429:
                with _DEEPL_LOCK:
                    DeepLFreeTranslator._consecutive_429s = min(DeepLFreeTranslator._consecutive_429s + 1, 10)
                    DeepLFreeTranslator._blocked_until = time.time() + 60
                return TranslationResult(self.name, src_code, dst_code, "", error="DeepL (free) rate limit (429)")
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))


# =============================================================================
# OFFICIAL DeepL API implementation (paid / free API keys)
# =============================================================================

DEEPL_API_URL = "https://api.deepl.com/v2/translate"
DEEPL_API_FREE_URL = "https://api-free.deepl.com/v2/translate"


class DeepLAPITranslator(Translator):
    """Official DeepL API client.
    Requires a DeepL API key (config.deepl_api_key).
    Supports both paid (api.deepl.com) and free API keys (api-free.deepl.com).
    """
    name = "DeepL"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or config.deepl_api_key
        if not self.api_key:
            raise ValueError("DeepL API key is required for paid mode")

        # Allow user to override the base URL (useful for free API keys)
        if base_url:
            self.base_url = base_url
        else:
            configured = getattr(config, "deepl_api_base_url", None)
            if configured:
                self.base_url = configured
            else:
                # Heuristic: if the key looks like a free key, use api-free
                # DeepL free keys usually end with ":fx"
                if self.api_key.endswith(":fx"):
                    self.base_url = DEEPL_API_FREE_URL
                else:
                    self.base_url = DEEPL_API_URL

        self.client = httpx.Client(timeout=20.0, headers={
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "User-Agent": "TranslationAggregator-Python/1.0",
        })

    def _lang_code(self, lang: Language | str, is_src: bool = False) -> str:
        code = self._get_lang(lang).upper()
        if is_src and code == "ZH-TW":
            code = "ZH"
        if code == "AUTO":
            return "" if not is_src else ""   # DeepL API uses empty or omit for auto
        # Map some codes
        mapping = {
            "ZH-CN": "ZH",
            "ZH-TW": "ZH",
        }
        return mapping.get(code, code)

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._lang_code(src, is_src=True)
        dst_code = self._lang_code(dst)

        if src_code and src_code == dst_code:
            return TranslationResult(self.name, src_code or "auto", dst_code, text)

        payload = {
            "text": [text],
            "target_lang": dst_code,
        }
        if src_code:
            payload["source_lang"] = src_code

        try:
            # DeepL API accepts both form and json; json is cleaner
            resp = self.client.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            j = resp.json()
            translations = j.get("translations", [])
            out = translations[0].get("text", "") if translations else ""
            return TranslationResult(self.name, src_code or "auto", dst_code, out, raw=j)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else "?"
            msg = f"DeepL API error (HTTP {status})"
            try:
                err = e.response.json()
                if "message" in err:
                    msg = f"DeepL API: {err['message']}"
            except Exception:
                pass
            return TranslationResult(self.name, src_code or "auto", dst_code, "", error=msg)
        except Exception as e:
            return TranslationResult(self.name, src_code or "auto", dst_code, "", error=str(e))


# =============================================================================
# Public class used everywhere in the app
# =============================================================================

class DeepLTranslator(Translator):
    """
    Smart DeepL translator.

    Chooses implementation based on config:

        deepl_mode == "api" and deepl_api_key present  → DeepLAPITranslator (official)
        otherwise                                      → DeepLFreeTranslator (web scraping)

    You can also force a specific backend by using the concrete classes directly:
        DeepLFreeTranslator()
        DeepLAPITranslator(api_key="...")
    """

    def __new__(cls, *args, **kwargs):
        mode = getattr(config, "deepl_mode", "free")
        key = getattr(config, "deepl_api_key", "") or ""

        if mode == "api":
            if not key:
                # User explicitly wants API but didn't provide a key.
                # Return a stub that gives a clear error on first use.
                class _DeepLMissingKey(Translator):
                    name = "DeepL (API)"
                    def translate(self, text, src="auto", dst="en"):
                        return TranslationResult(
                            self.name, str(src), str(dst), "",
                            error="DeepL API mode selected but no API key is configured. "
                                  "Set config.deepl_api_key or use the Settings dialog."
                        )
                return _DeepLMissingKey()
            try:
                return DeepLAPITranslator(api_key=key)
            except Exception as e:
                # Bad key or other init error → fall back with explanation
                class _DeepLApiInitFailed(Translator):
                    name = "DeepL (API)"
                    def __init__(self, err):
                        self._err = str(err)
                    def translate(self, text, src="auto", dst="en"):
                        return TranslationResult(
                            self.name, str(src), str(dst), "",
                            error=f"Failed to initialize DeepL API: {self._err}"
                        )
                return _DeepLApiInitFailed(e)

        # Free / default
        return DeepLFreeTranslator()

    name = "DeepL"

    def __init__(self, *args, **kwargs):
        pass

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        return TranslationResult(self.name, str(src), str(dst), "", error="DeepLTranslator misconfigured")
