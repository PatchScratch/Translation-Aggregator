from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from .base import Translator, Language, TranslationResult
from .translators import (
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
    BaiduTranslator,
    YandexTranslator,
)
from .substitutions import apply_substitutions, auto_hiragana


DEFAULT_TRANSLATORS = [
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
]


class TranslatorAggregator:
    def __init__(self, translators: Optional[List[Translator]] = None):
        if translators is None:
            translators = [cls() for cls in DEFAULT_TRANSLATORS]
        self.translators = translators

    def translate(
        self,
        text: str,
        src: Language | str = Language.AUTO,
        dst: Language | str = Language.English,
        max_workers: int = 8,
        profile: str | None = None,
    ) -> List[TranslationResult]:
        # Preprocess like original (substitutions + optional auto-hiragana)
        processed = auto_hiragana(text, str(src))
        processed = apply_substitutions(processed, profile)

        results: List[TranslationResult] = []

        def _run(t: Translator) -> TranslationResult:
            return t.translate(processed, src=src, dst=dst)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run, t): t for t in self.translators}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    t = futures[fut]
                    results.append(TranslationResult(t.name, str(src), str(dst), "", error=str(e)))

        # preserve original order
        order = {id(t): i for i, t in enumerate(self.translators)}
        results.sort(key=lambda r: order.get(id(next((tt for tt in self.translators if tt.name == r.translator), None)), 999))
        return results
