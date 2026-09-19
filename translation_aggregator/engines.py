"""Single translator registry for CLI, aggregator, and GUI."""
from __future__ import annotations

from typing import Dict, List, Type

from .base import Translator
from .config import AppConfig
from .translators import (
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
    BaiduTranslator,
    BaiduPlaywrightTranslator,
    YandexTranslator,
    WwwjdicTranslator,
    OpenAICompatTranslator,
)

TRANSLATOR_MAP: Dict[str, Type[Translator]] = {
    "google": GoogleTranslator,
    "bing": BingTranslator,
    "deepl": DeepLTranslator,
    "baidu": BaiduTranslator,
    "baidu_pw": BaiduPlaywrightTranslator,
    "yandex": YandexTranslator,
    "wwwjdic": WwwjdicTranslator,
    "openai": OpenAICompatTranslator,
}

DISPLAY_NAMES = {
    "google": "Google",
    "bing": "Bing",
    "deepl": "DeepL",
    "baidu": "Baidu",
    "baidu_pw": "Baidu (Playwright)",
    "yandex": "Yandex",
    "wwwjdic": "WWWJDIC",
    "openai": "OpenAI",
}

DEFAULT_ENABLED = ["google", "bing", "deepl", "yandex", "wwwjdic"]


def make_translator(name: str, cfg: AppConfig | None = None) -> Translator:
    key = name.strip().lower()
    cls = TRANSLATOR_MAP.get(key)
    if cls is None:
        raise KeyError(f"Unknown translator: {name}")
    if key == "wwwjdic":
        mirror = getattr(cfg, "wwwjdic_mirror", "") if cfg else ""
        return WwwjdicTranslator(mirror=mirror or WwwjdicTranslator.__init__.__defaults__[0])  # type: ignore
    if key == "openai":
        return OpenAICompatTranslator(
            base_url=getattr(cfg, "openai_base_url", "https://api.openai.com/v1") if cfg else "https://api.openai.com/v1",
            api_key=getattr(cfg, "openai_api_key", "") if cfg else "",
            model=getattr(cfg, "openai_model", "gpt-4o-mini") if cfg else "gpt-4o-mini",
            system_prompt=getattr(cfg, "openai_system_prompt", "") or OpenAICompatTranslator.__init__.__kwdefaults__["system_prompt"],  # type: ignore
        )
    return cls()


def translators_from_config(cfg: AppConfig) -> List[Translator]:
    names = list(cfg.enabled_translators or DEFAULT_ENABLED)
    out: List[Translator] = []
    for name in names:
        try:
            out.append(make_translator(name, cfg))
        except KeyError:
            continue
    return out or [GoogleTranslator()]
