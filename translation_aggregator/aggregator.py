from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from .base import Translator, Language, TranslationResult
from .engines import DEFAULT_ENABLED, make_translator
from .substitutions import apply_substitutions, auto_hiragana


class TranslatorAggregator:
    def __init__(self, translators: Optional[List[Translator]] = None):
        if translators is None:
            translators = [make_translator(n) for n in DEFAULT_ENABLED if n != "openai"]
        self.translators = translators

    def translate(
        self,
        text: str,
        src: Language | str = Language.AUTO,
        dst: Language | str = Language.English,
        max_workers: int = 8,
        profile: str | None = None,
    ) -> List[TranslationResult]:
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

        name_order = {t.name: i for i, t in enumerate(self.translators)}
        results.sort(key=lambda r: name_order.get(r.translator, 999))
        return results
