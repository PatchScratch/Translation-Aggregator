from __future__ import annotations

import re
import urllib.parse
from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

# Detect if Playwright is available (optional browser backend)
try:
    import playwright  # noqa: F401
    _PLAYWRIGHT_AVAILABLE = True
except Exception:
    _PLAYWRIGHT_AVAILABLE = False


class BaiduTranslator(Translator):
    name = "Baidu"

    def __init__(self, client: Optional[httpx.Client] = None):
        super().__init__()
        self.client = client or httpx.Client(timeout=20.0, follow_redirects=True)

    def _lang_code(self, lang: Language | str, is_src: bool = False) -> str:
        code = self._get_lang(lang)
        mapping = {
            "zh-CN": "zh",
            "zh-TW": "cht",
            "en": "en",
            "ja": "jp",
            "ko": "kor",
            "fr": "fra",
            "es": "spa",
            "ru": "ru",
            "de": "de",
            "it": "it",
            "pt": "pt",
        }
        return mapping.get(code, code)

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._lang_code(src, is_src=True)
        dst_code = self._lang_code(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        lang_map = {
            "ja": "jp",
            "zh": "zh",
            "zh-CN": "zh",
            "zh-TW": "cht",
            "en": "en",
        }
        from_code = lang_map.get(src_code, src_code)
        to_code = lang_map.get(dst_code, dst_code)
        lang_param = f"{from_code}2{to_code}"

        # If Playwright is available, use the real browser path (this is the reliable way
        # to use the exact mtpe-individual/transText endpoint the user confirmed works).
        if _PLAYWRIGHT_AVAILABLE:
            try:
                out = _baidu_playwright_fetch(text, lang_param)
                return TranslationResult(self.name, src_code, dst_code, out)
            except Exception as e:
                # Fall through to the plain HTTP attempt (will likely give the JS-only error)
                pass

        # --- Plain HTTP path (will almost always fail for this particular Baidu page) ---
        url = "https://fanyi.baidu.com/mtpe-individual/transText"
        params = {"query": text, "lang": lang_param}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://fanyi.baidu.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,zh-CN;q=0.7",
        }

        try:
            self.client.get("https://fanyi.baidu.com/", headers=headers)
            resp = self.client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            html = resp.text

            candidates: list[str] = []

            for m in re.finditer(
                r'<(?:span|div|p)[^>]*class="[^"]*(?:result|trans|target|output|dst)[^"]*"[^>]*>([^<]{12,400})</',
                html, re.I
            ):
                t = m.group(1).strip()
                if t:
                    candidates.append(t)

            for m in re.finditer(r'<(?:span|div|p)[^>]*>([^<]{12,350})</', html, re.I):
                t = m.group(1).strip()
                if t:
                    candidates.append(t)

            for blob in re.findall(r'\{[^{}]{10,600}\}', html):
                for key in ("dst", "trans", "result", "translation", "target"):
                    m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', blob)
                    if m:
                        candidates.append(m.group(1))

            for m in re.findall(r'([A-Z][a-z]{2,}[a-z ,.!?\'"-]{15,220})', html):
                candidates.append(m)

            out = ""
            src_l = text.lower()
            junk = (
                "script to run", "you need to enable", "setautopageview", "_hmt",
                "cache-control", "expires", "compatible", "pdf", "word",
                "在线", "翻译", "pageview", "control", "account", "noscript",
                "aria-", "hidden", "color", "style=", "class="
            )

            for c in candidates:
                c = c.strip()
                if len(c) < 15 or len(c) > 250:
                    continue
                cl = c.lower()
                if " " not in c or not re.search(r'[a-z].*[a-z]', c):
                    continue
                if not c[0].isupper():
                    continue
                if any(j in cl for j in junk):
                    continue
                if any(x in c for x in ("function", "var ", "window.", "document.", "=>", "<", "{", "}", "style=")):
                    continue
                if any(ord(ch) > 0x3000 for ch in c):
                    continue
                if src_l[:5] in cl or src_l[-5:] in cl:
                    continue
                if len(c.split()) < 3:
                    continue
                out = c
                break

            if out:
                return TranslationResult(self.name, src_code, dst_code, out, raw={"url": str(resp.url)})

            return TranslationResult(
                self.name, src_code, dst_code, "",
                error="Baidu: loaded mtpe-individual/transText but the translation is only rendered by JavaScript (no static result in HTML). "
                      "Install the [browser] extra (playwright) for reliable Baidu support.",
            )

        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=f"Baidu error: {e}")


# ---------------- Playwright-backed implementation (optional) ----------------

def _baidu_playwright_fetch(text: str, lang_param: str, timeout_ms: int = 25000) -> str:
    """
    Use a real browser (via Playwright) to load the mtpe-individual/transText page
    and wait for the translation result to appear in the DOM.

    Returns the extracted translation text, or raises on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(
            "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
        ) from e

    url = "https://fanyi.baidu.com/mtpe-individual/transText"
    query = urllib.parse.urlencode({"query": text, "lang": lang_param})
    full_url = f"{url}?{query}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = context.new_page()
        page.goto(full_url, wait_until="domcontentloaded", timeout=timeout_ms)

        # Heavy SPA: wait for network to settle
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

        # Try common result-like selectors
        selectors = [
            '[class*="result"]',
            '[class*="trans"]',
            '[class*="target"]',
            '[class*="output"]',
            '[class*="dst"]',
            'div[contenteditable="false"]',
            'span[contenteditable="false"]',
        ]

        result_text = ""
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc and loc.is_visible():
                    txt = (loc.inner_text() or "").strip()
                    if txt and len(txt) > 8:
                        result_text = txt
                        break
            except Exception:
                continue

        # Fallback: scan visible text for a plausible English sentence
        if not result_text:
            try:
                body_text = page.locator("body").inner_text() or ""
                candidates = re.findall(r'([A-Z][a-z]{2,}[a-z ,.!?\'"-]{12,280})', body_text)
                src_l = text.lower()
                for c in candidates:
                    c = c.strip()
                    cl = c.lower()
                    if len(c) < 12:
                        continue
                    if any(x in cl for x in ("script to run", "you need to enable", "pageview", "control", "account")):
                        continue
                    if any(ord(ch) > 0x3000 for ch in c[:60]):
                        continue
                    if src_l[:5] in cl or src_l[-5:] in cl:
                        continue
                    result_text = c
                    break
            except Exception:
                pass

        browser.close()

        if not result_text:
            raise RuntimeError("Playwright loaded the page but could not find a translation result in the DOM")

        # Strip Baidu MT UI toolbar labels that commonly leak into result containers
        # (seen by user: "编辑译文 段落对照 笔记")
        def _clean_baidu_text(t: str) -> str:
            if not t:
                return ""
            baidu_ui_phrases = {
                "编辑译文", "段落对照", "笔记",
                "复制", "朗读", "分享", "反馈", "编辑", "收起", "展开",
                "原文", "译文", "对照", "段落", "查看更多", "收起更多"
            }
            # Remove exact matches and lines containing only these
            lines = [ln.strip() for ln in t.splitlines()]
            kept = []
            for ln in lines:
                if not ln:
                    continue
                ln_stripped = ln.strip()
                if ln_stripped in baidu_ui_phrases:
                    continue
                low = ln_stripped.lower()
                if any(p.lower() in low for p in baidu_ui_phrases):
                    # Drop lines that are mostly the toolbar text
                    # but keep if they contain substantial translation content
                    if len(ln_stripped) < 25:
                        continue
                kept.append(ln_stripped)

            cleaned = "\n".join(kept).strip()

            # Final pass: remove the phrases even if inline
            for p in sorted(baidu_ui_phrases, key=len, reverse=True):
                cleaned = cleaned.replace(p, "").strip()

            # Collapse extra whitespace/newlines
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
            cleaned = re.sub(r' {2,}', ' ', cleaned)
            return cleaned.strip()

        result_text = _clean_baidu_text(result_text)

        return result_text


class BaiduPlaywrightTranslator(Translator):
    """
    Baidu translator backed by a real browser (Playwright).

    This loads the exact mtpe-individual/transText page the user confirmed works
    in their browser, waits for JS to render the result, and extracts it.

    Requires: pip install playwright && playwright install chromium
    (or the [browser] extra)
    """

    name = "Baidu"

    def __init__(self):
        super().__init__()

    def _lang_code(self, lang: Language | str, is_src: bool = False) -> str:
        code = self._get_lang(lang)
        mapping = {
            "zh-CN": "zh",
            "zh-TW": "cht",
            "en": "en",
            "ja": "jp",
            "ko": "kor",
            "fr": "fra",
            "es": "spa",
            "ru": "ru",
            "de": "de",
            "it": "it",
            "pt": "pt",
        }
        return mapping.get(code, code)

    def translate(self, text: str, src: Language | str = Language.AUTO, dst: Language | str = Language.English) -> TranslationResult:
        src_code = self._lang_code(src, is_src=True)
        dst_code = self._lang_code(dst)

        if src_code == dst_code and src_code != "auto":
            return TranslationResult(self.name, src_code, dst_code, text)

        lang_map = {
            "ja": "jp",
            "zh": "zh",
            "zh-CN": "zh",
            "zh-TW": "cht",
            "en": "en",
        }
        from_code = lang_map.get(src_code, src_code)
        to_code = lang_map.get(dst_code, dst_code)
        lang_param = f"{from_code}2{to_code}"

        try:
            out = _baidu_playwright_fetch(text, lang_param)
            return TranslationResult(self.name, src_code, dst_code, out)
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=f"Baidu (playwright): {e}")
