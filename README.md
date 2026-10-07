# Translation Aggregator

A modern, cross-platform rebuild of the classic Windows **Translation
Aggregator** — and it goes beyond the original: 15 translation engines
(including the local ATLAS and LEC engines), parallel translation, a fully
rearrangeable pane layout with tear-off windows, per-engine settings,
clipboard auto-translation, history navigation, and System/Light/Dark
themes. Everything the original did — except text hooking.

Runs on Windows and Linux (macOS best-effort). Free software under
GPL-2.0-or-later.

---

## Contents

- [Features](#features)
- [Engines](#engines)
- [Install](#install)
- [Local engines (ATLAS, LEC)](#local-engines-atlas-and-lec)
- [Using the app](#using-the-app)
- [Command line](#command-line)
- [Configuration](#configuration)
- [Dictionaries (JParser)](#dictionaries-jparser)
- [Performance notes](#performance-notes)
- [Limitations](#limitations)
- [Developing](#developing)
- [Credits](#credits)
- [License](#license)

## Features

**Translation**
- 15 engines in parallel: panes fill in as each engine answers — a slow
  engine never delays the others
- Translate from/to any supported language pair (Tools → Translate
  From / To), with auto-detect where the engine supports it
- Auto Clipboard mode: watch the clipboard and translate new text the
  moment it appears; rapid changes are queued, not dropped
- History navigation (Alt+Left / Alt+Right) over your submitted lines
- JParser dictionary pane: readings above every word, hover for the
  gloss, full conjugation handling — pure Python, loads in seconds
- MeCab pane: tokenization with furigana
- OpenAI-compatible chat engines (OpenAI, OpenRouter, LM Studio, ...)

**Layout**
- 1, 2, or 3 columns; drag any pane anywhere, drop panes into empty
  columns, drag a pane out of the window to tear it off into a
  borderless floating pane, drag it back to re-dock
- Close any pane (including JParser/MeCab) — re-open it from Settings
- Pane arrangement and column choice persist across restarts
- Always on top, window opacity, lockable pane order, selectable pane
  font

**Interface**
- Menu bar (File / View / Tools / Help) with keyboard shortcuts
- Each pane with settings has its own ⚙ button (DeepL, WWWJDIC,
  OpenAI, Caiyun, JParser, MeCab, ATLAS)
- System / Light / Dark color scheme, following your OS setting by
  default
- Convert source text to hiragana / katakana / romaji (Tools menu)
- Optional text substitutions and romaji→hiragana auto-conversion

## Engines

| Pane | CLI key | Type | Notes |
|---|---|---|---|
| Google Translate | `google` | MT | Free endpoint with automatic failover when rate-limited |
| Bing | `bing` | MT | ~1 s |
| DeepL | `deepl` | MT | Free web mode, or official API with your key (pane ⚙) |
| Yandex | `yandex` | MT | ~1 s |
| Papago | `papago` | MT | Naver's translator, ~1 s |
| Caiyun 彩云小译 | `caiyun` | MT | Official API; test token by default, add your own in the pane ⚙ |
| Systran | `systran` | MT | Official API via the free page's credentials, auto-detect |
| Babelfish | `babelfish` | MT | ~1 s |
| Baidu (Playwright) | `baidu_pw` | MT | Real browser; see [performance notes](#performance-notes) |
| ATLAS V14 | — | local MT | ja⇄en, needs ATLAS installed (Windows) |
| LEC Nova | `lec` | local MT | ja→en, needs Power Translator 15 (Windows) |
| WWWJDIC | `wwwjdic` | dictionary | Word breakdown with readings; mirror selectable |
| Jisho | `jisho` | dictionary | jisho.org word lookup |
| Babylon | `babylon` | dictionary | Multi-dictionary lookup (Wikipedia, bilingual glossaries) |
| OpenAI-compatible | `openai` | LLM | Any chat-completions endpoint (pane ⚙ for URL/key/model) |

Local engines appear as panes like the others; the registry keys above
are for the CLI and the Settings dialog.

## Install

**Prebuilt downloads** (no Python needed): the
[releases page](https://github.com/PatchScratch/Translation-Aggregator/releases)
carries a Windows build (`TranslationAggregator-x.y.z-win64.exe`) and a
Linux AppImage (`TranslationAggregator-x.y.z-x86_64.AppImage` — make it
executable and run; `--cli` inside the AppImage runs the command line
tool).

**MeCab in the portable builds:** the MeCab dictionary is large, so it is not
bundled — the MeCab pane starts with a "not available" notice. Install it
from inside the app: **Tools → Install MeCab (MeCab pane)…** downloads the
tokenizer and the unidic-lite dictionary once per user (about 50 MB, stored
outside the app next to its config, so it survives app updates) and the pane
starts working on the next translation. In the portable builds the optional
Playwright backend still cannot self-install — use the pip installation
below for the Baidu engine.

Or install from source. Requires Python 3.9+ (3.11+ recommended).
Windows, Linux, or macOS.

```bash
git clone https://github.com/PatchScratch/Translation-Aggregator
cd Translation-Aggregator
python -m venv .venv
.venv/Scripts/activate        # Windows   (Linux/macOS: .venv/bin/activate)
pip install -e ".[full]"
```

Then run the GUI:

```bash
transagg-gui
```

Optional extras instead of `full`: `[gui]` (no MeCab/Playwright),
`[mecab]`, `[browser]` (Playwright, only needed for the Baidu engine).
The GUI's Tools menu can install MeCab at any time (same fugashi +
unidic-lite packages, into the per-user extras directory):

```bash
pip install -e ".[gui]"
```

If you use the Baidu (Playwright) engine, also install the browser once
per machine (~150 MB):

```bash
playwright install chromium
```

The JParser dictionaries (`edict2`, `enamdict.gz`,
`Conjugations.txt`) ship with the repository — nothing to download.

## Local engines (ATLAS and LEC)

The original Translation Aggregator's local engines work here too:

- **ATLAS V14** (Fujitsu): install ATLAS to its default location
  (`C:\Program Files (x86)\ATLAS V14`). Translates Japanese→English and
  English→Japanese.
- **LEC Nova** (Power Translator 15): install Power Translator 15 to
  its default location. Japanese→English (the Nova engine DLL is
  one-way).

Both engines are 32-bit DLLs, so the app drives them through a small
bridge process that needs a **32-bit Python**:

1. Install a 32-bit Python (any recent 3.x) — the standard python.org
   installer offers it as a separate download.
2. Make sure the `py` launcher sees it (`py --list` shows a `-32`
   entry), or point the `TA_ATLAS_32_PYTHON` environment variable at
   its `python.exe`.

No packages are needed inside the 32-bit Python — the bridge only uses
the standard library.

## Using the app

1. Paste or type Japanese text in the source box (or tick **Auto
   Clipboard** and just copy text anywhere).
2. Press **Translate** (or Ctrl+Return). Every enabled pane updates in
   parallel.
3. Arrange the panes however you like:
   - drag a pane's header onto another pane or an empty column to move
     it
   - drag a pane out of the window to tear it off; drag its header back
     over the window to dock it
   - ✕ closes a pane; Settings → Translators re-opens it
4. The **Tools** menu switches languages, walks history, and converts
   the source text; the **View** menu controls always-on-top, opacity,
   columns, fonts, and layout lock.

## Command line

```bash
transagg "日本語の文章です" -s ja -d en --translators google,deepl,papago
```

`--translators` takes the CLI keys from the engine table above. The
default set is `google,bing,deepl,yandex,wwwjdic`.

## Configuration

Settings live in `~/.config/TranslationAggregator/config.json` (or a
`TranslationAggregator.ini` in the working directory, the classic
name). Everything is also editable from the GUI: the Settings dialog,
per-pane ⚙ dialogs, and the menu bar. Persisted state includes:

- enabled engines, pane arrangement, column count, color scheme
- language pair, auto-clipboard, substitutions
- ATLAS/LEC setup, DeepL/Caiyun/OpenAI keys, WWWJDIC mirror
- always-on-top, opacity, pane font

## Dictionaries (JParser)

JParser reads the classic TA dictionary files from `dictionaries/`:
`Conjugations.txt`, `edict2` (or `edict2.gz`), and optionally any
`edict`/`enamdict` (plain or `.gz`). All three ship in the repository.
Drop in updated EDRDG files any time — they are picked up on the next
start.

## Performance notes

- All engines translate in parallel; the typical line is translated by
  every fast engine (~1 s) while slower ones finish later into their
  own panes.
- **Baidu (Playwright) is slow — 10–20+ seconds per translation.**
  Baidu's page sends each translation through a private API call locked
  with a per-request security token generated by obfuscated JavaScript
  on the page. There is no way to call that API directly, so the engine
  drives a real browser and waits for the page itself to render the
  result. The app keeps one browser running in the background (about
  500 MB of memory); nothing else waits on it. If you don't need it,
  untick it in Settings — the other engines answer in about a second.
- JParser loads ~1.5 million dictionary entries in a few seconds and
  uses a few hundred MB of memory.

## Limitations

- **No text hooking / DLL injection.** The original's AGTH-style
  process hooking is Windows-specific and out of scope; use a separate
  text hooker (e.g. Textractor) plus Auto Clipboard mode.
- Local engines (ATLAS, LEC) are Windows-only 32-bit software.
- Free web endpoints can rate-limit; each pane reports errors plainly
  and the others keep working.

## Roadmap

- **User-defined AI engine panes.** Add your own AI translator panes
  from the GUI: point them at any OpenAI-style chat-completions API
  and pick a model, so you can run several AI translators side by side
  (different providers, different models, different prompts) — each
  as its own pane with its own settings, alongside the built-in
  engines.
- **More AI provider APIs.** Support for other AI API styles beyond
  OpenAI's — for example Anthropic's Messages API — so any AI
  provider can be added as a translator pane.
- More engines, more dictionaries, and per-pane translation history
  browsing.

## Developing

```bash
git clone https://github.com/PatchScratch/Translation-Aggregator
cd Translation-Aggregator
python -m venv .venv && .venv/Scripts/activate   # or .venv/bin/activate
pip install -e ".[full]"
transagg-gui
```

Layout of the package:

```
translation_aggregator/
├── base.py, engines.py      # Translator interface + engine registry
├── translators/             # one module per engine
├── jparser.py, mecab.py     # parser panes
├── atlas.py, atlas_bridge.py, lec_bridge.py   # local engines (32-bit bridges)
├── gui/
│   ├── window.py            # main window: panes, layout, drag&drop, menu actions
│   ├── stage1.py            # GUI shell + parallel translation worker
│   ├── menubar.py, theme.py # menu bar, color schemes
│   └── *_config_dialog.py   # per-pane settings dialogs
├── cli.py                   # transagg
└── config.py, history.py    # persistence
```

The upstream C++ project (behavioral reference for JParser, ATLAS and
the LEC engine calls):
https://github.com/Translation-Aggregator/Translation-Aggregator

## Credits

- The original **Translation Aggregator** and its contributors.
- Dictionary data from the **EDRDG** files (edict2, enamdict,
  Conjugations) — see the EDRDG licence terms in the dictionaries.
- jisho.org, Babylon, and the free translation endpoints this app
  drives.
- MeCab / unidic-lite for tokenization; PyQt6 for the GUI.

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
