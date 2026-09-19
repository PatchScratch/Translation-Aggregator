# Translation Aggregator (Python)

Cross-platform Python + PyQt6 port of Translation Aggregator.
Primary platforms: Windows and Linux. macOS is best-effort.

This repository is no longer a C++ application. The original Windows tree was a behavioral reference; portable pieces live in `translation_aggregator/` and `docs/extracted-from-cpp.md`. Upstream C++ if you still need hooks or ATLAS source: https://github.com/Translation-Aggregator/Translation-Aggregator

## Stage 1 slice

- Web MT: Google, Bing, DeepL, Baidu, Yandex
- WWWJDIC, JParser, MeCab
- OpenAI-compatible chat API (OpenAI, LM Studio, …)
- No injection, no LEC, no ATLAS in this slice

If `exe/`, `dll/`, or `Shared/` are still in your working tree, see `docs/remove-cpp.md`.

## Install and run

See [README_PYTHON.md](README_PYTHON.md).

```bash
pip install -e ".[gui]"
transagg-gui
```
