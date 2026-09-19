# Extracted from the C++ tree

The Win32 / inject / ATLAS / LEC sources are not part of this project anymore.
Behavioral recipes taken out before removal are below. Upstream C++ reference:
https://github.com/Translation-Aggregator/Translation-Aggregator

## WWWJDIC (`exe/TranslationWindows/HttpWindows/JdicWindow.cpp`)

- Japanese → English only.
- Request: `GET {mirror}?9ZIG{text}` (path suffix `?9ZIG` concatenated with the raw sentence).
- Default mirror: `http://wwwjdic.se/cgi-bin/wwwjdic.cgi`
- Other mirrors that shipped in the dialog:
  - `http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi`
  - `http://wwwjdic.biz/cgi-bin/wwwjdic`
  - `http://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic`
  - `https://gengo.com/wwwjdic/cgi-data/wwwjdic`
- Parse: substring between `<BODY>` and `</BODY>`, then unescape HTML.
- Blue/red `<font>` coloring is display-only; stage 1 returns plain text.

## HTTP MT engines

Each `*Window.cpp` is a host + path + POST template + `FindTranslatedText` scrape.
Python already has Google, Bing, DeepL, Baidu, Yandex. Dead in changelog: Honyaku, FreeTranslation, OCN. LEC Online / Babelfish treated as dead.

## Filters (`exe/Filter.cpp`) — ported to `translation_aggregator/filters.py`

Used on hooked text and on the clipboard-as-context. Stage 1 can run them on the source box if enabled later.

- infinite / constant / auto-constant / auto-advanced / custom char-repeat
- phrase extension basic + aggressive
- phrase repeat (min/max distance, defaults 4–100)
- line-break remove all / keep first N and last M

Hook injector itself is **not** ported.

## JParser / MeCab / dictionaries

Keep `dictionaries/Conjugations.txt` and edict files. Algorithm lives in `translation_aggregator/jparser.py` and `mecab.py`.

## History (`exe/History`)

Entry id + original string + map of translator-id → result, trim by count and ~20 MB of originals. Python `history.py` is still a simpler JSON log.

## Not extracted (deferred)

Injection, AGTH, internal hooks, context manager, menu translation, ATLAS DLL load, LEC, TAPlugin PE API, GDI furigana, WinHTTP, layout hotkeys.
