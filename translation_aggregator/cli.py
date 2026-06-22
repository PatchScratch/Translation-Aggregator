from __future__ import annotations

import argparse
import sys
from typing import List

from . import TranslatorAggregator, Language
from .base import TranslationResult


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Translation Aggregator (Python port)")
    parser.add_argument("text", help="Text to translate")
    parser.add_argument("-s", "--src", default="auto", help="Source language (default auto)")
    parser.add_argument("-d", "--dst", default="en", help="Target language (default en)")
    parser.add_argument(
        "-t", "--translators",
        default="google,bing,deepl",
        help="Comma separated list of translators (google,bing,deepl,baidu,baidu_pw,yandex). baidu_pw uses Playwright (real browser) for Baidu mtpe-individual."
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout")
    args = parser.parse_args(argv)

    wanted = [x.strip().lower() for x in args.src.split(",") if x.strip()]
    from .translators import (
        GoogleTranslator, BingTranslator, DeepLTranslator, BaiduTranslator, BaiduPlaywrightTranslator, YandexTranslator
    )
    registry = {
        "google": GoogleTranslator,
        "bing": BingTranslator,
        "deepl": DeepLTranslator,
        "baidu": BaiduTranslator,
        "baidu_pw": BaiduPlaywrightTranslator,
        "yandex": YandexTranslator,
    }

    translators = []
    for name in args.translators.split(","):
        name = name.strip().lower()
        if name in registry:
            translators.append(registry[name]())

    if not translators:
        translators = [GoogleTranslator()]

    agg = TranslatorAggregator(translators)
    results: List[TranslationResult] = agg.translate(args.text, src=args.src, dst=args.dst)

    for r in results:
        if r.error:
            print(f"[{r.translator}] ERROR: {r.error}")
        else:
            print(f"[{r.translator}] {r.text}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
