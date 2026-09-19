"""Port of exe/Filter.cpp. Operates on Python strings."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from typing import List, Sequence

DEFAULT_PHRASE_MIN = 4
DEFAULT_PHRASE_MAX = 100

CHAR_REPEAT_NONE = "none"
CHAR_REPEAT_AUTO_CONSTANT = "auto_constant"
CHAR_REPEAT_INFINITE = "infinite"
CHAR_REPEAT_AUTO_ADVANCED = "auto_advanced"
CHAR_REPEAT_CUSTOM = "custom"

PHRASE_EXTENSION_NONE = "none"
PHRASE_EXTENSION_BASIC = "basic"
PHRASE_EXTENSION_AGGRESSIVE = "aggressive"

PHRASE_REPEAT_NONE = "none"
PHRASE_REPEAT_AUTO = "auto"
PHRASE_REPEAT_CUSTOM = "custom"

LINE_BREAK_KEEP = "keep"
LINE_BREAK_REMOVE = "remove"
LINE_BREAK_REMOVE_SOME = "remove_some"


@dataclass
class FilterSettings:
    char_repeat_mode: str = CHAR_REPEAT_NONE
    custom_repeats: List[int] = field(default_factory=list)
    phrase_extension_mode: str = PHRASE_EXTENSION_NONE
    phrase_repeat_mode: str = PHRASE_REPEAT_NONE
    phrase_min: int = DEFAULT_PHRASE_MIN
    phrase_max: int = DEFAULT_PHRASE_MAX
    line_break_mode: str = LINE_BREAK_KEEP
    line_breaks_first: int = 0
    line_breaks_last: int = 0
    japanese_only: bool = False


def infinite_repeat_filter(s: str) -> str:
    if not s:
        return s
    out = [s[0]]
    for ch in s[1:]:
        if ch != out[-1]:
            out.append(ch)
    return "".join(out)


def constant_repeat_filter(s: str, repeat: int) -> str:
    if repeat <= 1:
        return s
    return s[::repeat]


def auto_constant_repeat_filter(s: str) -> str:
    if not s:
        return s
    count = 1
    repeat = 0
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            count += 1
        else:
            repeat = gcd(count, repeat) if repeat else count
            count = 1
    repeat = gcd(count, repeat) if repeat else count
    return constant_repeat_filter(s, repeat)


def phrase_repeat_filter(
    s: str, min_dist: int = DEFAULT_PHRASE_MIN, max_dist: int = DEFAULT_PHRASE_MAX
) -> str:
    if not s:
        return s
    out: List[str] = []
    temp_min = min_dist
    last_dist = 0
    i = 0
    n = len(s)
    while i < n:
        hit_dist = 0
        hit_count = 0
        d = temp_min
        while d < max_dist and i + 2 * d <= n:
            count = 1
            pos = i + d
            chunk = s[i : i + d]
            while pos + d <= n and s[pos : pos + d] == chunk:
                pos += d
                count += 1
            if count > 1 and hit_dist * hit_count < d * count:
                hit_dist = d
                hit_count = count
            d += 1
        if hit_dist:
            last_dist = hit_dist
            temp_min = hit_dist
            i += hit_dist * (hit_count - 1)
            continue
        temp_min = min_dist
        if last_dist:
            while last_dist > 1 and i < n:
                out.append(s[i])
                i += 1
                last_dist -= 1
            if i >= n:
                break
        out.append(s[i])
        i += 1
    return "".join(out)


def line_break_remove_all(s: str) -> str:
    return s.replace("\n", "")


def line_break_remove_some(s: str, first: int, last: int) -> str:
    if first <= 0 and last <= 0:
        return line_break_remove_all(s)
    parts = s.split("\n")
    keep_head = parts[:first] if first else []
    keep_tail = parts[-last:] if last else []
    mid = parts[first : len(parts) - last if last else None]
    mid_joined = "".join(mid)
    chunks: List[str] = []
    if keep_head:
        chunks.append("\n".join(keep_head))
    chunks.append(mid_joined)
    if keep_tail:
        chunks.append("\n".join(keep_tail))
    return "\n".join(x for x in chunks if x != "" or keep_head or keep_tail)


def _has_japanese(s: str) -> bool:
    return any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF or 0xFF66 <= ord(c) <= 0xFF9D for c in s)


def auto_filter(s: str, settings: FilterSettings | None = None) -> str:
    settings = settings or FilterSettings()
    if settings.japanese_only and not _has_japanese(s):
        return ""
    text = s.replace("\r\n", "\n").replace("\r", "\n")
    mode = settings.char_repeat_mode
    if mode == CHAR_REPEAT_AUTO_CONSTANT:
        text = auto_constant_repeat_filter(text)
    elif mode == CHAR_REPEAT_INFINITE:
        text = infinite_repeat_filter(text)
    elif mode == CHAR_REPEAT_CUSTOM:
        reps = [r for r in settings.custom_repeats if r > 0]
        if len(reps) == 1:
            text = constant_repeat_filter(text, reps[0])
        else:
            text = infinite_repeat_filter(text)
    if settings.phrase_repeat_mode == PHRASE_REPEAT_AUTO:
        text = phrase_repeat_filter(text)
    elif settings.phrase_repeat_mode == PHRASE_REPEAT_CUSTOM:
        if settings.phrase_min > 0 and settings.phrase_max > settings.phrase_min:
            text = phrase_repeat_filter(text, settings.phrase_min, settings.phrase_max)
    if settings.line_break_mode == LINE_BREAK_REMOVE:
        text = line_break_remove_all(text)
    elif settings.line_break_mode == LINE_BREAK_REMOVE_SOME:
        text = line_break_remove_some(text, settings.line_breaks_first, settings.line_breaks_last)
    return text
