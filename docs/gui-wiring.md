# GUI wiring after pull

`window.py` still has a local `TRANSLATOR_MAP`. After `git pull`, change these two spots so new engines appear as panes.

1. Replace the translator import and map:

```python
from ..translators import GoogleTranslator, BingTranslator, DeepLTranslator, BaiduTranslator, BaiduPlaywrightTranslator, YandexTranslator
```

with:

```python
from ..engines import TRANSLATOR_MAP, make_translator, DISPLAY_NAMES
```

and delete the old `TRANSLATOR_MAP = { ... }` block.

2. Where a translator instance is built from a key, use `make_translator(key, config)` instead of `TRANSLATOR_MAP[key]()`.

CLI already works without that edit:

```bash
python -m translation_aggregator.cli "こんにちは" -t google,wwwjdic
```
