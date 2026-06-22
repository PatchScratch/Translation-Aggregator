from __future__ import annotations

import re
from typing import List, Tuple, Dict

from .config import config


def apply_substitutions(text: str, profile: str | None = None) -> str:
    """
    Apply pre-translation substitutions.
    Universal profile is "*", plus the specific game/profile if provided.
    Each entry is [old, rep].
    """
    subs: List[Tuple[str, str]] = []
    if config.enable_substitutions and config.substitutions:
        subs.extend(config.substitutions.get("*", []))
        if profile:
            subs.extend(config.substitutions.get(profile, []))
    for old, rep in subs:
        if not old:
            continue
        try:
            text = re.sub(re.escape(old), rep, text)
        except Exception:
            # fallback literal
            text = text.replace(old, rep)
    return text


def auto_hiragana(text: str, src_lang: str) -> str:
    if not config.auto_hiragana:
        return text
    if src_lang not in ("ja", "Japanese", "japanese"):
        return text
    # Only if it looks like romaji (very rough)
    if re.search(r"[a-zA-Z]", text) and not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text):
        try:
            from pykakasi import kakasi  # optional
            k = kakasi()
            k.setMode("H", "H")
            conv = k.getConverter()
            return conv.do(text)
        except Exception:
            pass
    return text
