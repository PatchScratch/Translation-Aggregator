"""OpenAI-compatible chat-completions translator (OpenAI, LM Studio, proxies)."""
from __future__ import annotations

from typing import Optional

import httpx

from ..base import Translator, Language, TranslationResult

DEFAULT_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_PROMPT = (
    "Translate the user text from {src} to {dst}. "
    "Return only the translation. Preserve line breaks."
)


class OpenAICompatTranslator(Translator):
    name = "OpenAI"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_PROMPT,
        client: Optional[httpx.Client] = None,
    ):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.client = client or httpx.Client(timeout=60.0, follow_redirects=True)

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
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        prompt = self.system_prompt.format(src=src_code, dst=dst_code)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        }
        try:
            resp = self.client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return TranslationResult(self.name, src_code, dst_code, (content or "").strip(), raw=data)
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))
