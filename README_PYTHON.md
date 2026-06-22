# Translation Aggregator (Python Port)

Cross-platform reimplementation of the core of Translation Aggregator.

## What works today

- Multiple web translators in parallel (Google, Bing, DeepL, Baidu, Yandex, ...)
- Pre-translation substitutions + auto half-width/full + auto-romaji→hiragana
- JParser (pure Python): edict/edict2/enamdict loading, conjugation stripping, matching
- MeCab integration (mecab-python3 or system `mecab` binary)
- ATLAS via native Windows DLLs (stub) or via Wine + helper script
- PyQt6 GUI that mirrors the classic multi-pane layout + source box + auto-clipboard
- CLI for headless use
- JSON config + history

## Installation

```bash
# Core (translators + JParser + CLI)
pip install -e .

# With GUI
pip install -e ".[gui]"

# With MeCab support
pip install -e ".[mecab]"

# With browser backend (Playwright) - required for reliable Baidu support
pip install -e ".[browser]"
# then install the browser:
playwright install chromium

# Everything (GUI + MeCab + Browser/Playwright for Baidu)
pip install -e ".[full]"
# then install the browser:
playwright install chromium
```

GUI requires PyQt6:
```bash
pip install PyQt6
# or the [gui] extra above
```

MeCab:
- Windows: `pip install mecab-python3 unidic-lite` or install MeCab + `libmecab.dll`
- Linux/macOS: install `mecab` + `mecab-ipadic` (or unidic) via package manager, then `pip install mecab-python3`

Browser backend (Playwright):
- Required for reliable Baidu support (the `mtpe-individual/transText` endpoint is a JavaScript-rendered SPA).
- Install the optional extra:
  ```bash
  pip install -e ".[browser]"
  ```
- Install the browser binaries (Chromium is recommended and sufficient):
  ```bash
  playwright install chromium
  ```
- What you get:
  - `BaiduTranslator` (the default "baidu") will **automatically** use the real browser backend when Playwright is detected.
  - You can also explicitly select the browser backend with `baidu_pw` (CLI: `-t baidu_pw`) or the "baidu_pw" checkbox in the GUI.
- Without Playwright installed, Baidu falls back to a plain HTTP fetch. This usually only gets the static shell of the page and will return a clear error message instead of a blank result.
- System note: `playwright install chromium` downloads a Chromium browser (~150-200 MB). You only need to do this once per machine.

## Run

CLI:
```bash
transagg "日本語の文章です" -s ja -d en --translators google,deepl
```

GUI:
```bash
transagg-gui
# or
python -m translation_aggregator.gui.main
```

## Cross-platform notes & limitations

- Web translators: fully cross-platform.
- JParser: fully cross-platform (loads same Conjugations.txt + edict files).
- MeCab: cross-platform via bindings or CLI.
- ATLAS: on Windows can try native; elsewhere use Wine + `atlas_wine_helper.py` (you must have ATLAS installed inside a Wine prefix).
- **No** text hooking / DLL injection / AGTH-style features on non-Windows (those are Windows-only).
- Clipboard monitoring and hotkeys are best on the platform where the GUI runs (global hotkeys may need extra OS support).

## Dictionaries for JParser

Put `edict2`, `edict`, or `enamdict` (plain or .gz) + `Conjugations.txt` into the `dictionaries/` directory (same files as the original).

## ATLAS via Wine (example)

1. Have a working Wine prefix with ATLAS V13/V14 installed.
2. Copy or symlink `atlas_wine_helper.py` inside that prefix where python can run it.
3. Set `TA_ATLAS_WINE_HELPER` or edit the path in `atlas.py`.
4. Run the GUI on the host; ATLAS pane will call into Wine.

## Configuration

- `TranslationAggregator.ini` (classic name) or `~/.config/TranslationAggregator/config.json`
- JParser flags, enabled translators, substitution lists, etc. are stored here.
- GUI has a Settings dialog.

## Original

This is a functional port of the *useful* parts. The original Windows-specific hooking, injection, and full GUI chrome are not replicated 1:1.

Original project: https://github.com/Translation-Aggregator/Translation-Aggregator
