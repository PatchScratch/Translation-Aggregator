from __future__ import annotations

import gzip
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from .config import config

# --- Faithful port of C++ constants and structures from Dictionary.h / Config.h ---

# JAP_WORD_* flags (subset used for scoring/display in JParser path)
JAP_WORD_PRIMARY     = 0x0001
JAP_WORD_PRONOUNCE   = 0x0002
JAP_WORD_COMMON_LINE = 0x0004
JAP_WORD_COMMON      = 0x0008
JAP_WORD_PART        = 0x0010
JAP_WORD_COUNTER     = 0x0020
JAP_WORD_TOP         = 0x0040
JAP_WORD_FINAL       = 0x8000

# MATCH_IS_*
MATCH_IS_NAME = 0x0001

# JPARSER flags (from Config.h) - we mirror the ones that affect matching/display
JPARSER_DISPLAY_VERB_CONJUGATIONS = 0x01
JPARSER_JAPANESE_OWN_LINE         = 0x02
JPARSER_SINGLE_KANJI              = 0x04
JPARSER_SINGLE_HIRAGANA           = 0x08
JPARSER_USE_MECAB                 = 0x10

# MeCab position flags used in FindBestMatches (Dictionary.cpp)
MECAB_BAD_END   = 0x01
MECAB_BAD_START = 0x02

MAX_CONJ_DEPTH = 4  # matches C++ Match.conj[MAX_CONJ_DEPTH]

# Exact tense name order from C++ staticTenses (Dictionary.cpp)
STATIC_TENSES = [
    "Non-past", "Past", "Conjunctive", "Provisional", "Potential",
    "Passive", "Causative", "Imperative", "Volitional", "Negative",
    "Conjectural", "Continuative", "TENSE_REMOVE", "Stem"
]

# Map from Conjugations.txt "Tense" values to our canonical names
TENSE_ALIAS = {
    "Remove": "TENSE_REMOVE",
    "remove": "TENSE_REMOVE",
}

# Tense IDs (must match order in Conjugations.txt + static list in C++)
TENSE_NON_PAST   = 0
TENSE_PAST       = 1
TENSE_CONJ       = 2
TENSE_PROVISIONAL= 3
TENSE_POTENTIAL  = 4
TENSE_PASSIVE    = 5
TENSE_CAUSATIVE  = 6
TENSE_IMPERATIVE = 7
TENSE_VOLITIONAL = 8
TENSE_NEGATIVE   = 9
TENSE_CONJECTURAL=10
TENSE_CONTINUATIVE=11
TENSE_REMOVE     =12
TENSE_STEM       =13


# --- Public helpers required by GUI (and used internally for furigana) ---
def to_hiragana(text: str) -> str:
    """Convert katakana to hiragana (pass-through if already hiragana)."""
    if not text:
        return text
    return "".join(
        chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c
        for c in text
    )


def to_katakana(text: str) -> str:
    """Convert hiragana to katakana (pass-through if already katakana)."""
    if not text:
        return text
    return "".join(
        chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c
        for c in text
    )


_ROMAJI_TABLE = {
    'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
    'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
    'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
    'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
    'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
    'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
    'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
    'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
    'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
    'わ': 'wa', 'を': 'wo', 'ん': 'n',
    'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
    'きゃ': 'kya', 'きゅ': 'kyu', 'きょ': 'kyo',
    'しゃ': 'sha', 'しゅ': 'shu', 'しょ': 'sho',
    'ちゃ': 'cha', 'ちゅ': 'chu', 'ちょ': 'cho',
    'にゃ': 'nya', 'にゅ': 'nyu', 'にょ': 'nyo',
    'ひゃ': 'hya', 'ひゅ': 'hyu', 'ひょ': 'hyo',
    'みゃ': 'mya', 'みゅ': 'myu', 'みょ': 'myo',
    'りゃ': 'rya', 'りゅ': 'ryu', 'りょ': 'ryo',
    'ぎゃ': 'gya', 'ぎゅ': 'gyu', 'ぎょ': 'gyo',
    'じゃ': 'ja', 'じゅ': 'ju', 'じょ': 'jo',
    'びゃ': 'bya', 'びゅ': 'byu', 'びょ': 'byo',
    'ぴゃ': 'pya', 'ぴゅ': 'pyu', 'ぴょ': 'pyo',
    'っ': '',
}


def to_romaji(text: str) -> str:
    """Small Hepburn romaji for readings."""
    if not text:
        return ""
    h = to_hiragana(text)
    out = []
    i = 0
    n = len(h)
    while i < n:
        if h[i] == 'っ' and i + 1 < n:
            next_char = h[i + 1]
            cons_map = {
                'か': 'k', 'き': 'k', 'く': 'k', 'け': 'k', 'こ': 'k',
                'さ': 's', 'し': 's', 'す': 's', 'せ': 's', 'そ': 's',
                'た': 't', 'ち': 't', 'つ': 't', 'て': 't', 'と': 't',
                'は': 'h', 'ひ': 'h', 'ふ': 'h', 'へ': 'h', 'ほ': 'h',
                'ま': 'm', 'み': 'm', 'む': 'm', 'め': 'm', 'も': 'm',
                'や': 'y', 'ゆ': 'y', 'よ': 'y',
                'ら': 'r', 'り': 'r', 'る': 'r', 'れ': 'r', 'ろ': 'r',
                'わ': 'w',
                'が': 'g', 'ぎ': 'g', 'ぐ': 'g', 'げ': 'g', 'ご': 'g',
                'ざ': 'z', 'じ': 'z', 'ず': 'z', 'ぜ': 'z', 'ぞ': 'z',
                'だ': 'd', 'ぢ': 'd', 'づ': 'd', 'で': 'd', 'ど': 'd',
                'ば': 'b', 'び': 'b', 'ぶ': 'b', 'べ': 'b', 'ぼ': 'b',
                'ぱ': 'p', 'ぴ': 'p', 'ぷ': 'p', 'ぺ': 'p', 'ぽ': 'p',
            }
            out.append(cons_map.get(next_char, next_char))
            i += 1
            continue
        if i + 1 < n:
            dig = h[i:i + 2]
            if dig in _ROMAJI_TABLE:
                out.append(_ROMAJI_TABLE[dig])
                i += 2
                continue
        ch = h[i]
        out.append(_ROMAJI_TABLE.get(ch, ch))
        i += 1
    return "".join(out)


@dataclass
class Conj:
    """Matches ConjInfo in Dictionary.h (verbType/verbTense/verbConj/verbForm)."""
    verb_type: int = 0
    verb_tense: int = 0
    verb_conj: int = 0
    verb_form: int = 0


# --- Public helpers required by GUI (and used internally for furigana) ---
def to_hiragana(text: str) -> str:
    """Convert katakana to hiragana (pass-through if already hiragana)."""
    if not text:
        return text
    return "".join(
        chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c
        for c in text
    )


def to_katakana(text: str) -> str:
    """Convert hiragana to katakana (pass-through if already katakana)."""
    if not text:
        return text
    return "".join(
        chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c
        for c in text
    )


_ROMAJI_TABLE = {
    'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
    'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
    'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
    'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
    'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
    'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
    'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
    'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
    'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
    'わ': 'wa', 'を': 'wo', 'ん': 'n',
    'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
    'きゃ': 'kya', 'きゅ': 'kyu', 'きょ': 'kyo',
    'しゃ': 'sha', 'しゅ': 'shu', 'しょ': 'sho',
    'ちゃ': 'cha', 'ちゅ': 'chu', 'ちょ': 'cho',
    'にゃ': 'nya', 'にゅ': 'nyu', 'にょ': 'nyo',
    'ひゃ': 'hya', 'ひゅ': 'hyu', 'ひょ': 'hyo',
    'みゃ': 'mya', 'みゅ': 'myu', 'みょ': 'myo',
    'りゃ': 'rya', 'りゅ': 'ryu', 'りょ': 'ryo',
    'ぎゃ': 'gya', 'ぎゅ': 'gyu', 'ぎょ': 'gyo',
    'じゃ': 'ja', 'じゅ': 'ju', 'じょ': 'jo',
    'びゃ': 'bya', 'びゅ': 'byu', 'びょ': 'byo',
    'ぴゃ': 'pya', 'ぴゅ': 'pyu', 'ぴょ': 'pyo',
    'っ': '',  # gemination handled separately
}


def to_romaji(text: str) -> str:
    """Very small Hepburn romaji converter for typical dictionary readings."""
    if not text:
        return ""
    h = to_hiragana(text)
    out = []
    i = 0
    n = len(h)
    while i < n:
        # small tsu doubles next consonant
        if h[i] == 'っ' and i + 1 < n:
            next_char = h[i + 1]
            cons_map = {
                'か': 'k', 'き': 'k', 'く': 'k', 'け': 'k', 'こ': 'k',
                'さ': 's', 'し': 's', 'す': 's', 'せ': 's', 'そ': 's',
                'た': 't', 'ち': 't', 'つ': 't', 'て': 't', 'と': 't',
                'は': 'h', 'ひ': 'h', 'ふ': 'h', 'へ': 'h', 'ほ': 'h',
                'ま': 'm', 'み': 'm', 'む': 'm', 'め': 'm', 'も': 'm',
                'や': 'y', 'ゆ': 'y', 'よ': 'y',
                'ら': 'r', 'り': 'r', 'る': 'r', 'れ': 'r', 'ろ': 'r',
                'わ': 'w',
                'が': 'g', 'ぎ': 'g', 'ぐ': 'g', 'げ': 'g', 'ご': 'g',
                'ざ': 'z', 'じ': 'z', 'ず': 'z', 'ぜ': 'z', 'ぞ': 'z',
                'だ': 'd', 'ぢ': 'd', 'づ': 'd', 'で': 'd', 'ど': 'd',
                'ば': 'b', 'び': 'b', 'ぶ': 'b', 'べ': 'b', 'ぼ': 'b',
                'ぱ': 'p', 'ぴ': 'p', 'ぷ': 'p', 'ぺ': 'p', 'ぽ': 'p',
            }
            cons = cons_map.get(next_char, next_char)
            out.append(cons)
            i += 1
            continue

        # try digraph first
        if i + 1 < n:
            dig = h[i:i + 2]
            if dig in _ROMAJI_TABLE:
                out.append(_ROMAJI_TABLE[dig])
                i += 2
                continue

        ch = h[i]
        out.append(_ROMAJI_TABLE.get(ch, ch))
        i += 1

    return "".join(out)


@dataclass
class Conj:
    """Matches ConjInfo in Dictionary.h (verbType/verbTense/verbConj/verbForm)."""
    verb_type: int = 0   # 1-based into verb_types
    verb_tense: int = 0
    verb_conj: int = 0
    verb_form: int = 0

@dataclass
class Match:
    """Matches the C++ Match struct used for JParser results."""
    start: int
    len: int
    src_len: int
    jap: str
    reading: str
    gloss: str
    conj: List[Conj] = field(default_factory=list)
    flags: int = 0
    is_name: bool = False
    inexact_match: int = 0
    jap_flags: int = 0
    dict_index: int = 0


class JParser:
    """
    Pure-Python reimplementation of the core JParser logic from TA.

    Loads:
      - dictionaries/Conjugations.txt (same file)
      - any edict / edict2 / enamdict in dictionaries/ (plain or .gz)

    It does not use the .bin format; it parses text dictionaries at startup.
    """

    def __init__(self, dict_dir: Optional[str] = None, use_mecab: bool = True):
        self.dict_dir = Path(dict_dir or config.dictionaries_dir)
        self.use_mecab = use_mecab and config.jparser_use_mecab
        self.furigana_mode = (getattr(config, "jparser_furigana", None) or "none").lower()

        self.verb_types: List[dict] = []
        self.tense_names: List[str] = []
        self.entries: Dict[str, List[dict]] = {}  # surface -> list of {"reading": , "gloss": , "flags": }

        self._load_conjugations()
        self._build_conj_table_postprocess()
        self._load_dictionaries()
        self._tag_verb_stems_from_remove_suffixes()  # emulate CreateDict verbType stem creation

        self._mecab = None
        if self.use_mecab:
            try:
                from .mecab import MecabWrapper
                self._mecab = MecabWrapper()
            except Exception:
                self._mecab = None

    # ---------- loading ----------

    def _load_conjugations(self):
        """Load exactly like C++ LoadConjugationTable + post-processing for next_verb_type_id and remove_tense."""
        path = self.dict_dir / "Conjugations.txt"
        if not path.exists():
            for p in [Path("dictionaries/Conjugations.txt"), Path("../dictionaries/Conjugations.txt")]:
                if p.exists():
                    path = p
                    break
        if not path.exists():
            self.verb_types = []
            self.tense_names = []
            return

        raw = path.read_bytes()
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("utf-8", errors="replace")
        data = json.loads(text)

        self.tense_names = list(STATIC_TENSES)

        self.verb_types = []
        for item in data:
            name = item.get("Name")
            pos = item.get("Part of Speech", "Verb")
            tenses = item.get("Tenses", [])
            vtype = {
                "name": name,
                "is_adj": pos == "Adj",
                "remove_tense": TENSE_NON_PAST,
                "conjugations": []
            }
            for t in tenses:
                tn = t.get("Tense", "Non-past")
                tn = TENSE_ALIAS.get(tn, tn)
                c = {
                    "suffix": t.get("Suffix", ""),
                    "tense": tn,
                    "formal": bool(t.get("Formal")),
                    "negative": bool(t.get("Negative")),
                    "next_type": t.get("Next Type", ""),
                    "next_verb_type_id": 0,
                }
                vtype["conjugations"].append(c)
            self.verb_types.append(vtype)

        # Post-process like C++: set remove_tense and next_verb_type_id
        for vt in self.verb_types:
            for c in vt["conjugations"]:
                tid = self._tense_id(c["tense"])
                if tid == TENSE_REMOVE:
                    vt["remove_tense"] = TENSE_REMOVE

        for vt_idx, vt in enumerate(self.verb_types):
            for c in vt["conjugations"]:
                nxt = c.get("next_type") or ""
                if not nxt:
                    continue
                for vt2_idx, vt2 in enumerate(self.verb_types, 1):
                    if vt2.get("name") != nxt:
                        continue
                    for c2 in vt2["conjugations"]:
                        if c2.get("tense") in ("Non-past", "Stem") and not c2.get("formal") and not c2.get("negative"):
                            suf = c.get("suffix", "")
                            suf2 = c2.get("suffix", "")
                            if suf.endswith(suf2):
                                c["next_verb_type_id"] = vt2_idx
                                break
                    if c.get("next_verb_type_id"):
                        break

    def _tag_verb_stems_from_remove_suffixes(self):
        """Emulate the CreateDict pass that walks each entry, finds a verb type's 'remove' suffix,
        strips it from the surface, and creates a new JapString entry pointing at the same english
        but with verbType set (so FindMatches will later call FindVerbMatches for that vtype).
        """
        if not self.verb_types:
            return
        # For each vt find the conjugation used at build time to identify the plain stem:
        # the one with tenseID == remove_tense and form==0
        remove_map: List[Tuple[int, str]] = []
        for vt_idx, vt in enumerate(self.verb_types, 1):
            rt = vt.get('remove_tense', TENSE_NON_PAST)
            for c in vt.get('conjugations', []):
                if self._tense_id(c.get('tense', '')) == rt and not c.get('formal') and not c.get('negative'):
                    suf = c.get('suffix', '')
                    if suf:
                        remove_map.append((vt_idx, suf))
                    break
        if not remove_map:
            return

        to_add: Dict[str, List[dict]] = {}
        for surf, elist in list(self.entries.items()):
            for e in elist:
                for vt_idx, suf in remove_map:
                    sl = len(suf)
                    if sl and surf.endswith(suf):
                        stem = surf[:-sl]
                        if stem:
                            ne = dict(e)
                            ne['_verb_type'] = vt_idx
                            to_add.setdefault(stem, []).append(ne)
        for stem, elist in to_add.items():
            bucket = self.entries.setdefault(stem, [])
            for ne in elist:
                if not any(x.get('_verb_type') == ne.get('_verb_type') and x.get('reading') == ne.get('reading') for x in bucket):
                    bucket.append(ne)

        # Also handle verb types whose Remove has empty suffix (vs, vs-i, vs-s etc.).
        # In that case the surface *itself* is a valid stem (no stripping).
        for vt_idx, vt in enumerate(self.verb_types, 1):
            for c in vt.get('conjugations', []):
                if self._tense_id(c.get('tense', '')) == vt.get('remove_tense', TENSE_NON_PAST) and not c.get('formal') and not c.get('negative'):
                    if c.get('suffix', '') == '':
                        for surf, elist in list(self.entries.items()):
                            for e in elist:
                                if e.get('_verb_type') == vt_idx:
                                    continue
                                ne = dict(e)
                                ne['_verb_type'] = vt_idx
                                bucket = self.entries.setdefault(surf, [])
                                if not any(x.get('_verb_type') == vt_idx and x.get('reading') == ne.get('reading') for x in bucket):
                                    bucket.append(ne)
                    break

    def _load_dict_file(self, path: Path):
        opener = gzip.open if path.suffix == ".gz" else open
        mode = "rt"
        try:
            with opener(path, mode, encoding="euc-jp", errors="replace") as f:
                for line in f:
                    self._parse_edict_line(line)
        except UnicodeDecodeError:
            with opener(path, mode, encoding="utf-8", errors="replace") as f:
                for line in f:
                    self._parse_edict_line(line)

    def _parse_edict_line(self, line: str):
        line = line.strip()
        if not line or line.startswith(";") or line[0] in "\u3000\uff1f":
            return
        # format:  word [reading] /gloss1/gloss2/
        if "/" not in line:
            return
        head, rest = line.split("/", 1)
        head = head.strip()
        gloss = "/" + rest
        # remove trailing /
        if gloss.endswith("/"):
            gloss = gloss[:-1]

        # Capture optional [reading] even when after ; separated writings
        m = re.match(r"^(.+?)(?:\s*\[(.+?)\])?\s*$", head)
        if not m:
            return
        left = m.group(1).strip()
        reading = m.group(2).strip() if m.group(2) else None

        # split multiple writings on ;
        writings = [w.strip() for w in re.split(r"\s*;\s*", left) if w.strip()]
        if not writings:
            return
        if not reading:
            reading = writings[0]

        # crude flags
        flags = 0
        if "(P)" in gloss:
            flags |= 0x0008  # JAP_WORD_COMMON
        if "(suf)" in gloss or "(ctr)" in gloss:
            flags |= 0x0020  # JAP_WORD_COUNTER
        if re.search(r"\b(name|given|place|surname)\b", gloss, re.I):
            flags |= 0x0001  # name-ish

        for w in writings:
            entry = {"reading": reading, "gloss": gloss, "flags": flags}
            self.entries.setdefault(w, []).append(entry)
            # also index the reading as a surface (for pure-kana lookup)
            if reading and reading != w:
                self.entries.setdefault(reading, []).append(entry)

    def _load_dictionaries(self):
        self.entries.clear()
        if not self.dict_dir.exists():
            return
        for f in sorted(self.dict_dir.iterdir()):
            if f.is_file() and (f.suffix in (".txt", ".gz") or "edict" in f.name.lower() or "enam" in f.name.lower()):
                if f.name.lower().startswith("conjugations"):
                    continue
                try:
                    self._load_dict_file(f)
                except Exception:
                    pass

    # ---------- conjugation stripping (simplified but effective) ----------

    # ---------- faithful port of C++ matching (Dictionary.cpp FindMatches / FindVerbMatches / FindAllMatches / FindBestMatches / SortMatches) ----------

    def _build_conj_table_postprocess(self):
        """Mirror the post-processing in LoadConjugationTable for next_verb_type_id and remove_tense."""
        for vt_idx, vt in enumerate(self.verb_types):
            vt.setdefault('remove_tense', TENSE_NON_PAST)
            for c in vt.get('conjugations', []):
                tname = c.get('tense', '')
                tid = self._tense_id(tname)
                if tname == 'TENSE_REMOVE' or tid == TENSE_REMOVE:
                    vt['remove_tense'] = tid
            # stacking next_verb_type_id
            for c in vt.get('conjugations', []):
                nxt = c.get('next_type', '') or ''
                if not nxt:
                    c['next_verb_type_id'] = 0
                    continue
                found = 0
                for vt2_idx, vt2 in enumerate(self.verb_types, 1):
                    if vt2.get('name') != nxt:
                        continue
                    for c2 in vt2.get('conjugations', []):
                        if c2.get('tense', 'Non-past') in ('Non-past', 'Stem') and not c2.get('formal') and not c2.get('negative'):
                            suf = c.get('suffix', '')
                            suf2 = c2.get('suffix', '')
                            if suf.endswith(suf2) or (suf2 and suf.endswith(suf2[-len(suf2):] if len(suf2) <= len(suf) else '')):
                                c['next_verb_type_id'] = vt2_idx
                                found = 1
                                break
                    if found:
                        break
                if not found:
                    c['next_verb_type_id'] = 0

    def _tense_id(self, name: str) -> int:
        try:
            return self.tense_names.index(name)
        except ValueError:
            return 0

    def _lookup_surface(self, surface: str) -> List[dict]:
        return self.entries.get(surface, [])

    def _find_verb_matches(self, text_from_start: str, base_slen: int, vtype: int, depth: int = 0, inexact: int = 0) -> List[Match]:
        """Exact port of FindVerbMatches (Dictionary.cpp ~738-804).
        text_from_start: the slice of input starting at the position where the base stem match began.
        base_slen: the length of the stem that was already matched (corresponds to 'slen' in C++).
        Only suffixes that match starting at text_from_start[base_slen:] are considered.
        """
        out: List[Match] = []
        if vtype < 1 or vtype > len(self.verb_types):
            return out
        vt = self.verb_types[vtype-1]
        # In C++ 'string' points at the start of *this* FindMatches call; we match suffixes after slen.
        tail = text_from_start[base_slen:]
        for c_idx, conj in enumerate(vt.get('conjugations', [])):
            if conj.get('tense', '') == 'TENSE_REMOVE':
                continue
            suf = conj.get('suffix', '')
            slen = len(suf)
            if not suf or slen > len(tail) or not tail.startswith(suf):
                continue
            inex2 = inexact
            if suf and tail[:slen] != suf:
                inex2 = 1
            # The total matched length for this result is base + this suffix
            total_len = base_slen + slen
            c = Conj(verb_type=vtype,
                     verb_tense=self._tense_id(conj.get('tense', 'Non-past')),
                     verb_conj=c_idx,
                     verb_form=(int(conj.get('formal', False)) + int(conj.get('negative', False)) * 2))
            if not conj.get('next_verb_type_id'):
                # leaf: create one match record for this conjugation depth
                # We do not know the base reading/gloss here; caller will fill from the JapString hit.
                m = Match(start=0, len=total_len, src_len=total_len,
                          jap=text_from_start[:total_len],
                          reading=text_from_start[:total_len],
                          gloss='',
                          flags=0,
                          conj=[c] + [Conj() for _ in range(depth)],  # pad to depth
                          inexact_match=inex2,
                          jap_flags=0)
                # normalize conj list to have entries at [0..depth]
                while len(m.conj) <= depth:
                    m.conj.append(Conj())
                m.conj[depth] = c
                out.append(m)
            else:
                # stacking
                if depth and conj.get('tense') == 'Stem' and not conj.get('formal') and not conj.get('negative'):
                    added = self._find_verb_matches(text_from_start, total_len, conj['next_verb_type_id'], depth, inex2)
                    for mm in added:
                        while len(mm.conj) <= depth:
                            mm.conj.append(Conj())
                        mm.conj[depth] = c
                    out += added
                elif depth < MAX_CONJ_DEPTH - 1:
                    newly = self._find_verb_matches(text_from_start, total_len, conj['next_verb_type_id'], depth + 1, inex2)
                    for mm in newly:
                        # emulate "Potential Potential" removal
                        if (len(mm.conj) > depth + 1 and
                            mm.conj[depth + 1].verb_tense == self._tense_id(conj.get('tense', '')) and
                            self._tense_id(conj.get('tense', '')) == TENSE_POTENTIAL):
                            continue
                        while len(mm.conj) <= depth:
                            mm.conj.append(Conj())
                        mm.conj[depth] = c
                    out += newly
        return out

    def _find_matches(self, text: str, start: int) -> List[Match]:
        """Faithful emulation of FindMatches (Dictionary.cpp ~807) + FindVerbMatches extension.
        For every position, we find ALL prefix-matching surfaces (various lengths), set inexactMatch
        exactly like wcsnicmp, record japFlags/dictIndex equivalent, then for every such base hit we
        call the equivalent of FindVerbMatches on the *tail after the base slen* to attach conjugations
        and extend .len .
        """
        matches: List[Match] = []
        n = len(text) - start
        s = text[start:]
        maxl = min(12, n)
        # Collect for every length that has surface hits (C++ collects all that wcsnijcmp==0)
        for length in range(1, maxl + 1):
            substr = s[:length]
            cands = self._lookup_surface(substr)
            if not cands:
                continue
            for e in cands:
                rd = e.get('reading', substr)
                # Direct surface lookup via the written form key => exact match on the text that was looked up.
                # (Reading may legitimately differ; inexact is NOT based on reading.)
                inex = 0
                base = Match(start=start, len=length, src_len=length,
                             jap=substr, reading=rd, gloss=e.get('gloss',''),
                             flags=e.get('flags',0), inexact_match=inex, jap_flags=e.get('flags',0),
                             dict_index=0,
                             is_name=bool(e.get('flags',0) & 0x0001))
                matches.append(base)

                # If this surface was tagged at load time with a verbType (like CreateDict does),
                # call the *exact* FindVerbMatches port on the tail after this base length.
                vtype = e.get('_verb_type') or 0
                if vtype:
                    vms = self._find_verb_matches(s, length, vtype, 0, inex)
                    for vm in vms:
                        vm.start = start
                        vm.reading = rd
                        vm.gloss = e.get('gloss', '')
                        vm.jap = text[start : start + vm.len]
                        vm.jap_flags = base.jap_flags
                        vm.is_name = base.is_name
                        matches.append(vm)
                # Do NOT call _extend_with_verb_suffixes for untagged bases.
                # Only verb-typed stems (from _tag_verb_stems) legitimately extend via FindVerbMatches.

            # do NOT break: continue to longer lengths so that full conjugated surfaces or longer dictionary words are also considered (C++ increments len)
        # Also surface stripping matches (covers entries reached only via conjugation stripping)
        for stem, conjs in self._strip_conjugations(s):
            for e in self._lookup_surface(stem):
                rd = e.get('reading', stem)
                inex = 0 if stem == rd else 1
                m = Match(start=start, len=len(stem), src_len=len(s),
                          jap=stem, reading=rd, gloss=e.get('gloss',''),
                          flags=e.get('flags',0), conj=conjs, inexact_match=inex, jap_flags=e.get('flags',0),
                          is_name=bool(e.get('flags',0) & 0x0001))
                matches.append(m)
        return matches

    def _extend_with_verb_suffixes(self, text: str, base_start: int, base_len: int, base_inex: int, jap_flags: int, is_name: bool, base_reading: str = '', base_gloss: str = '') -> List[Match]:
        """Faithful port of the part of FindMatches that, after a base JapString hit, calls FindVerbMatches
        on the tail (string+slen, slen, jap->verbType, ...).
        This version is called from _find_matches when we have a surface hit.  It walks suffixes starting at
        text[base_start+base_len : ] exactly as the C++ code does.
        """
        out: List[Match] = []
        remaining_start = base_start + base_len
        remaining = text[remaining_start:]
        if not self.verb_types:
            return out

        for vt_idx, vt in enumerate(self.verb_types, 1):
            for c_idx, conj in enumerate(vt.get('conjugations', [])):
                if conj.get('tense', '') == 'TENSE_REMOVE':
                    continue
                suf = conj.get('suffix', '')
                sl = len(suf)
                if not suf or sl > len(remaining) or not remaining.startswith(suf):
                    continue
                inex2 = base_inex
                if suf and remaining[:sl] != suf:
                    inex2 = 1
                c = Conj(verb_type=vt_idx,
                         verb_tense=self._tense_id(conj.get('tense', 'Non-past')),
                         verb_conj=c_idx,
                         verb_form=(int(conj.get('formal', False)) + int(conj.get('negative', False)) * 2))
                full_len = base_len + sl
                base_jap = text[base_start:base_start + base_len]
                # C++: for verb matches, srcLen stays the base slen, len = slen + suffixLen
                m = Match(start=base_start, len=full_len, src_len=base_len,
                          jap=base_jap + remaining[:sl],
                          reading=base_reading or (base_jap + remaining[:sl]),
                          gloss=base_gloss or '',
                          flags=jap_flags,
                          conj=[c],
                          inexact_match=inex2,
                          jap_flags=jap_flags,
                          is_name=is_name)
                out.append(m)
                nxt = conj.get('next_verb_type_id') or 0
                if nxt:
                    out += self._extend_with_verb_suffixes(text, base_start, full_len, inex2, jap_flags, is_name, base_reading, base_gloss)
        # dedup
        seen = set()
        uniq = []
        for m in out:
            k = (m.start, m.len, tuple((c.verb_type, c.verb_tense, c.verb_conj, c.verb_form) for c in m.conj))
            if k not in seen:
                seen.add(k)
                uniq.append(m)
        return uniq

    def _find_all_matches(self, text: str) -> List[Match]:
        """Port of FindAllMatches."""
        allm: List[Match] = []
        n = len(text)
        for i in range(n):
            ms = self._find_matches(text, i)
            for m in ms:
                # adjust start already set inside
                allm.append(m)
        return allm

    def _find_best_matches(self, text: str, use_mecab_flag: bool) -> List[Match]:
        """Port of FindBestMatches (Dictionary.cpp ~1075). DP + MeCab BAD_START/BAD_END + reconstruction + SortMatches."""
        raw = self._find_all_matches(text)
        if not raw:
            return []
        n = len(text)
        pos_flags = [0] * n
        # Faithful MeCab penalty path (C++ MecabParseString + BAD_* flags)
        if use_mecab_flag and self._mecab:
            try:
                mecab_raw = self._mecab.parse(text)
                # C++ walks lines, splits on \t, aligns characters, then sets BAD_START/BAD_END for non-* katakana rows
                lines = mecab_raw.splitlines()
                pos = 0
                for line in lines:
                    if not line or line == 'EOS':
                        continue
                    if '\t' not in line:
                        continue
                    word, rest = line.split('\t', 1)
                    if not word:
                        continue
                    # align in source
                    old_pos = pos
                    match_len = 0
                    while pos < n and match_len < len(word) and text[pos] == word[match_len]:
                        match_len += 1
                        pos += 1
                    if match_len == len(word) and not (pos < n and word and text[pos-match_len:pos] != word):
                        # walk to katakana field (8th comma field after surface+features)
                        fields = rest.split(',')
                        # typical: surface \t pos,pos_detail1,... ,*,*,*,*, katakana ,...
                        # we only penalize when katakana field exists and is not '*'
                        kata = None
                        if len(fields) >= 8:
                            kata = fields[7] if len(fields) > 7 else None
                        if kata and kata not in ('*', ''):
                            # set BAD flags for this span
                            for i in range(match_len - 1):
                                if pos - match_len + i < n:
                                    pos_flags[pos - match_len + i] |= 0x01  # BAD_END
                                if pos - match_len + i + 1 < n:
                                    pos_flags[pos - match_len + i + 1] |= 0x02  # BAD_START
                    else:
                        pos = old_pos
            except Exception:
                pass

        class B:
            __slots__ = ('score', 'match_len', 'match_index')
            def __init__(self):
                self.score = 0
                self.match_len = 0
                self.match_index = -2

        best = [B() for _ in range(n + 1)]
        best[0].score = 0
        best[0].match_index = -2
        for i in range(1, n+1):
            best[i].score = 0x7fffffff
            best[i].match_index = -2

        # C++ walks the array produced by FindAllMatches (order of increasing start).
        # For the DP advancing matchIndex we need start/-len order; keep original for reconstruction.
        raw_for_dp = sorted(raw, key=lambda m: (m.start, -m.len))
        match_idx = 0
        pos = 0
        while pos < n:
            score = best[pos].score + 100
            if 0x4E00 <= ord(text[pos]) <= 0x9FBF:
                score += 400
            nxt = pos + 1
            if best[nxt].score > score:
                best[nxt].score = score
                best[nxt].match_index = -1
                best[nxt].match_len = 0

            while match_idx < len(raw_for_dp) and raw_for_dp[match_idx].start <= pos:
                m = raw_for_dp[match_idx]
                if m.start < pos:
                    match_idx += 1
                    continue
                if m.start > pos:
                    break
                sc = best[pos].score + 10
                if pos_flags[pos] & 0x02:   # MECAB_BAD_START
                    sc += 10
                if pos + m.len - 1 < n and (pos_flags[pos + m.len - 1] & 0x01):
                    sc += 10
                if m.jap_flags & JAP_WORD_PART:
                    sc -= 2
                elif m.len == 1:
                    sc += 1
                # digit continuity
                if pos > 0 and text[pos].isdigit() and text[pos-1].isdigit():
                    sc += 100
                if m.jap_flags & (JAP_WORD_COMMON | JAP_WORD_COMMON_LINE):
                    sc -= 3
                if m.inexact_match:
                    sc += 10
                # name katakana penalty (simplified faithful heuristic)
                if m.is_name or (m.jap_flags & 0x1):
                    mad = m.inexact_match
                    if not mad:
                        base = text[m.start:m.start + m.len]
                        if all(0x30A0 <= ord(c) <= 0x30FF for c in base):
                            mad = 0
                        else:
                            mad = 1
                    if mad:
                        sc += 500 * m.len
                    else:
                        sc += 5
                nxtp = pos + m.len
                if nxtp <= n and best[nxtp].score >= sc:
                    best[nxtp].score = sc
                    best[nxtp].match_len = m.len
                    best[nxtp].match_index = match_idx   # index into raw_for_dp (only used for best[] bookkeeping)
                match_idx += 1
            pos += 1

        # Exact port of reconstruction (Dictionary.cpp ~1282):
        # Use the ORIGINAL FindAllMatches order (raw) for collection,
        # scanning backwards exactly as C++ does with the original array.
        # This ensures the pre-SortMatches list has matches in the order
        # they appeared in FindAllMatches for the chosen spans.
        chosen: List[Match] = []
        index = len(raw) - 1
        pos = n
        while pos > 0:
            bi = best[pos]
            if bi.match_index < 0:
                while pos > 0 and best[pos].match_index < 0:
                    pos -= 1
                continue
            start = pos - bi.match_len
            ln = bi.match_len
            while index >= 0 and raw[index].start >= start:
                if raw[index].start == start and raw[index].len == ln:
                    chosen.append(raw[index])
                index -= 1
            pos = start
        chosen.reverse()

        # Now do the exact C++ post-processing: CompareIdenticalMatches + dedup + inexact sync, then CompareMatches sort
        self._sort_matches(chosen)
        return chosen

    def _sort_matches(self, matches: List[Match]):
        """Exact port of SortMatches + CompareIdenticalMatches + CompareMatches (Dictionary.cpp ~1025)."""
        # CompareIdenticalMatches qsort (by start, dictIndex, firstJString, then conj tuple)
        matches.sort(key=lambda m: (
            m.start,
            getattr(m, 'dict_index', 0),
            getattr(m, 'firstJString', 0) or 0,   # not used in our Match; kept for parity
            tuple((c.verb_type, c.verb_tense, c.verb_conj, c.verb_form) for c in m.conj) if m.conj else ()
        ))

        # Exact port of the dedup loop in SortMatches
        d = 0 if matches else 0
        i = 1 if matches else 0
        while i < len(matches):
            j = i
            k = d - 1
            while (k >= 0 and
                   getattr(matches[j], 'dict_index', 0) == getattr(matches[k], 'dict_index', 0) and
                   matches[j].start == matches[k].start and
                   matches[j].len == matches[k].len and
                   matches[j].inexact_match != matches[k].inexact_match):
                matches[j].inexact_match = matches[k].inexact_match = 0
                j = k
                if k > 0:
                    k -= 1
                else:
                    break
            # memcmp equivalent: if identical including conj[0], skip (C++ memcmp on whole struct)
            if d > 0 and all(getattr(matches[i], f, None) == getattr(matches[d-1], f, None)
                             for f in ('start','len','jap','reading','inexact_match','jap_flags','is_name','dict_index')) and \
               tuple((c.verb_type, c.verb_tense, c.verb_conj, c.verb_form) for c in (matches[i].conj or [])) == \
               tuple((c.verb_type, c.verb_tense, c.verb_conj, c.verb_form) for c in (matches[d-1].conj or [])):
                i += 1
                continue
            # special verb-vs-non-verb rule (C++): if same start/len, one has verbType and the other doesn't,
            # and the verb one is plain non-past form 0, drop the non-verb one
            if (d > 0 and
                matches[i].start == matches[d-1].start and
                matches[i].len == matches[d-1].len and
                getattr(matches[i], 'dict_index', 0) == getattr(matches[d-1], 'dict_index', 0) and
                (matches[i].conj and matches[i].conj[0].verb_type) and
                (not matches[d-1].conj or not matches[d-1].conj[0].verb_type) and
                matches[i].conj[0].verb_form == 0 and
                matches[i].conj[0].verb_tense == TENSE_NON_PAST and
                (i+1 == len(matches) or
                 matches[i+1].start != matches[i].start or
                 matches[i+1].len != matches[i].len or
                 getattr(matches[i+1], 'dict_index', 0) != getattr(matches[i], 'dict_index', 0))):
                i += 1
                continue
            matches[d] = matches[i]
            d += 1
            i += 1
        if d != len(matches):
            del matches[d:]

        # CompareMatches qsort (exact port)
        def key(m: Match):
            name = 1 if (m.is_name or (m.flags & MATCH_IS_NAME)) else 0
            mask = JAP_WORD_COUNTER | JAP_WORD_PART | JAP_WORD_COMMON | JAP_WORD_COMMON_LINE | JAP_WORD_PRIMARY
            flag_diff = -(m.jap_flags & mask)
            return (m.start,
                    m.inexact_match,
                    name,
                    flag_diff,
                    -getattr(m, 'dict_index', 0),
                    m.jap,
                    tuple((c.verb_type, c.verb_tense, c.verb_conj, c.verb_form) for c in m.conj) if m.conj else ())
        matches.sort(key=key)

    # ---------- end faithful port section ----------

    def _strip_conjugations(self, word: str) -> List[Tuple[str, List[Conj]]]:
        """
        Return list of (stem, conjugations) by trying to peel suffixes.
        Kept for compatibility; the faithful path uses _find_verb_matches too.
        """
        results: List[Tuple[str, List[Conj]]] = [(word, [])]
        if not self.verb_types:
            return results
        for vt_idx, vtype in enumerate(self.verb_types, 1):
            for c_idx, conj in enumerate(vtype.get("conjugations", [])):
                suf = conj.get("suffix", "")
                if not suf or not word.endswith(suf):
                    continue
                stem = word[: -len(suf)]
                if not stem:
                    continue
                c = Conj(verb_type=vt_idx, verb_tense=self._tense_id(conj.get("tense", "Non-past")),
                         verb_conj=c_idx, verb_form=(int(conj.get("formal", False)) + int(conj.get("negative", False)) * 2))
                results.append((stem, [c]))
                for stem2, cs in self._strip_conjugations(stem):
                    if stem2 != stem:
                        results.append((stem2, cs + [c]))
        seen = set()
        uniq = []
        for s, cs in results:
            key = (s, tuple((c.verb_type, c.verb_tense, c.verb_form) for c in cs))
            if key not in seen:
                seen.add(key)
                uniq.append((s, cs))
        return uniq

    # ---------- lookup ----------

    def find_matches(self, text: str) -> List[Match]:
        # For backward compatibility with any external caller; real JParser path now uses _find_best_matches.
        return self._find_all_matches(text)

    def _format_reading(self, reading: str) -> str:
        mode = getattr(self, "furigana_mode", "none") or "none"
        if mode == "hiragana":
            return to_hiragana(reading)
        if mode == "katakana":
            return to_katakana(reading)
        if mode == "romaji":
            return to_romaji(reading)
        return reading

    def format_match(self, m: Match) -> str:
        r = self._format_reading(m.reading)
        mode = getattr(self, "furigana_mode", "none") or "none"
        if mode == "none":
            return m.jap
        return f"{m.jap} [{r}]"

    def format_gloss(self, raw_gloss: str, conjs: List[Conj]) -> str:
        """Faithful formatting of the English gloss + optional conjugation for JParser display.
        Mirrors the original TA behavior controlled by jparser_* config flags.
        """
        cfg = config
        g = raw_gloss or ""

        # Strip sections based on hide_* (the original uses the same slash-delimited format)
        if getattr(cfg, "jparser_hide_pos", False):
            g = re.sub(r"\(n,.*?\)|\(v,.*?\)|\(adj.*?\)|\(adv.*?\)|\(prt.*?\)|\(int.*?\)|\(conj.*?\)", "", g, flags=re.I)
        if getattr(cfg, "jparser_hide_usage", False):
            g = re.sub(r"\(vi\)|\(vt\)|\(v5.*?\)|\(vs.*?\)|\(vk.*?\)|\(vn.*?\)|\(aux.*?\)", "", g, flags=re.I)
        if getattr(cfg, "jparser_hide_crossrefs", False):
            g = re.sub(r"See .*?\.", "", g, flags=re.I)

        # Reformat numbers like original (① ② etc. or (1) (2))
        if getattr(cfg, "jparser_reformat_numbers", False):
            g = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩]", lambda m: f"({ord(m.group(0))-0x2460+1})", g)
            g = re.sub(r"\((\d+)\)", r"(\1)", g)

        # Remove kana in brackets if requested
        if getattr(cfg, "jparser_no_kana_brackets", False):
            g = re.sub(r"\[.*?\]", "", g)

        # Keep only first N definition lines
        lines = [ln.strip() for ln in g.split("/") if ln.strip()]
        nlines = getattr(cfg, "jparser_definition_lines", 3) or 3
        if nlines > 0:
            lines = lines[:nlines]
        g = " / ".join(lines)

        # Append conjugation string exactly like C++ (tense name from the table)
        if getattr(cfg, "jparser_show_conj", False) and conjs:
            parts = []
            for c in conjs:
                if c.verb_type:
                    tname = self.tense_names[c.verb_tense] if 0 <= c.verb_tense < len(self.tense_names) else ""
                    # C++ prints the tense name; we can make it a bit more readable
                    if tname and tname not in ("TENSE_REMOVE", "Stem"):
                        parts.append(tname)
            if parts:
                g = (g + " (" + ", ".join(parts) + ")") if g else ("(" + ", ".join(parts) + ")")

        return g.strip(" /")

    def parse(self, text: str) -> List[Match]:
        """High level entry used by the GUI: runs the faithful C++-style BestMatch selection.
        MeCab (if enabled) is used only inside _find_best_matches for BAD_START/BAD_END penalties.
        The input text is never rewritten; doing so corrupts matching with feature strings.
        """
        use_mecab = bool(getattr(self, "use_mecab", True) and getattr(config, "jparser_use_mecab", True))
        best = self._find_best_matches(text, use_mecab)
        # C++ returns the full chosen list; GUI caps at 80 when building segments.
        return best
