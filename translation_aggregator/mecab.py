from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional, List

from .config import config


class MecabError(Exception):
    pass


class MecabWrapper:
    """
    Cross platform MeCab wrapper.
    Prefers mecab-python3 if available.
    Falls back to calling 'mecab' executable.
    """

    def __init__(self, mecab_path: Optional[str] = None):
        self._mecab = None
        self._use_subprocess = False
        self._mecab_cmd: List[str] = []

        explicit = mecab_path or config.mecab_path or os.environ.get("MECAB_PATH")
        if explicit:
            # user gave explicit
            pass

        # Try python binding first
        try:
            import MeCab  # type: ignore

            # mecab-python3 exposes Tagger
            self._mecab = MeCab.Tagger("")
            # quick sanity
            _ = self._mecab.parse("test")
            return
        except Exception:
            pass

        # Fallback to CLI
        candidates = ["mecab"]
        if explicit:
            candidates.insert(0, explicit)
        for c in candidates:
            if shutil.which(c) or os.path.exists(c):
                self._use_subprocess = True
                self._mecab_cmd = [c]  # default full output (surface + all feature fields) for faithful MeCab pane
                return

        raise MecabError("MeCab not found (install mecab or mecab-python3)")

    def parse(self, text: str) -> str:
        """Return full MeCab output (surface + all feature fields). Faithful to original TA."""
        if self._mecab is not None:
            return self._mecab.parse(text) or ""
        try:
            out = subprocess.check_output(
                self._mecab_cmd,
                input=text.encode("utf-8"),
                stderr=subprocess.DEVNULL,
            )
            return out.decode("utf-8", errors="replace")
        except Exception as e:
            raise MecabError(str(e))

    def parse_to_tokens(self, text: str) -> list[dict]:
        """
        Robust parse of MeCab full output.
        Handles both standard IPADIC (surface\tpos,feat,...,lemma,reading,pron)
        and some Japanese installs that emit tab-separated fields
        (e.g. surface\treading\t...\tbase\tpos...).
        Always populates: surface, lemma, reading (best kana for ruby), pron, raw, pos
        """
        raw = self.parse(text)
        tokens: list[dict] = []
        for line in raw.splitlines():
            line = line.rstrip("\r\n")
            if not line or line == "EOS":
                continue
            if "\t" not in line:
                continue
            surface, rest = line.split("\t", 1)

            lemma = ""
            reading = ""
            pron = ""
            pos = ""

            if "," in rest and "\t" not in rest:
                # Classic IPADIC comma format (surface\tpos,feat1,feat2,...,lemma,reading,pron)
                fields = rest.split(",")
                pos = fields[0] if fields else ""
                # In IPADIC the base form is usually field 6 (0-based after the pos fields), reading field 7
                # But to be safe we take the last non-* fields as reading/pron when present.
                for i in range(len(fields)-1, -1, -1):
                    f = fields[i]
                    if f and f not in ("*", "") and all(
                        (0x3040 <= ord(c) <= 0x30FF) or c in "ー・" for c in f
                    ):
                        reading = f
                        break
                # lemma/base is usually the first field after the POS details that looks like a base
                for i in range(1, len(fields)):
                    f = fields[i]
                    if f and f not in ("*", ""):
                        lemma = f
                        break
                if not lemma:
                    lemma = surface
                if not reading:
                    reading = lemma or surface
            else:
                # Tab-separated output (common on Japanese Windows MeCab installs)
                # Layout seen in the user's data:
                #   次	ツギ	ツギ	次	名詞-普通名詞-一般		2
                #   話	ハナシ	ハナシ	話	名詞-普通名詞-サ変可能		3
                #   公開	コーカイ	コウカイ	公開	名詞-普通名詞-サ変可能		0
                #   し	シ	スル	為る	動詞-非自立可能	サ行変格	連用形-一般	0
                #
                # Columns are usually:
                # 0: reading (katakana)   -- this is what MeCab decided to use for this token
                # 1: base/lemma (often same or kanji)
                # 2: surface or another form
                # 3: POS tag
                parts = rest.split("\t")
                # The very first field after surface is almost always the reading MeCab chose.
                if len(parts) >= 1:
                    p0 = parts[0].strip()
                    if p0 and p0 not in ("*", ""):
                        reading = p0
                # Lemma is the first field that contains kanji or is a good base form
                for p in parts:
                    p = p.strip()
                    if p and p not in ("*", "") and (any("\u4e00" <= c <= "\u9fbf" for c in p) or p != reading):
                        lemma = p
                        break
                if not lemma:
                    lemma = surface
                # pos is the first field that looks like a POS (contains ー or known tag)
                for p in parts:
                    p = p.strip()
                    if p and ("名詞" in p or "助詞" in p or "動詞" in p or "形容詞" in p or "助動詞" in p or "接頭" in p or "-" in p):
                        pos = p
                        break
                if not pos and len(parts) > 3:
                    pos = parts[3].strip()

            if not lemma:
                lemma = surface
            if not reading:
                reading = surface

            tokens.append({
                "surface": surface,
                "pos": pos or "",
                "lemma": lemma,
                "reading": reading,
                "pron": pron or reading,
                "raw": line,
            })
        return tokens
