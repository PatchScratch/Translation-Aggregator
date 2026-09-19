from __future__ import annotations

import argparse
import sys
from typing import List

from . import TranslatorAggregator, Language
from .base import TranslationResult
from .config import config
from .engines import TRANSLATOR_MAP, make_translator


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Translation Aggregator (Python port)")
    parser.add_argument("text", help="Text to translate")
    parser.add_argument("-s", "--src", default="ja", help="Source language (default ja)")
    parser.add_argument("-d", "--dst", default="en", help="Target language (default en)")
    parser.add_argument(
        "-t",
        "--translators",
        default="google,bing,deepl,yandex,wwwjdic",
        help="Comma list: google,bing,deepl,baidu,baidu_pw,yandex,wwwjdic,openai",
    )
    args = parser.parse_args(argv)

    translators = []
    for name in args.translators.split(","):
        name = name.strip().lower()
        if name in TRANSLATOR_MAP:
            translators.append(make_translator(name, config))

    if not translators:
        translators = [make_translator("google", config)]

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
