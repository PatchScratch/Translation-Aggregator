"""LEC Nova engine (Power Translator 15) via the 32-bit bridge.

The Nova JaEn engine DLL is 32-bit and one-way (Japanese -> English),
so this engine spawns lec_bridge.py under a 32-bit Python per call -
same pattern as the ATLAS engine.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..base import Translator, Language, TranslationResult


def _find_32bit_python() -> Optional[str]:
    """A 32-bit python for the bridge: TA_ATLAS_32_PYTHON or the py launcher."""
    env = os.environ.get("TA_ATLAS_32_PYTHON")
    if env and os.path.isfile(env):
        return env
    py = shutil.which("py")
    return py


class LecTranslator(Translator):
    name = "LEC"

    def __init__(self):
        super().__init__()
        self._bridge = str(Path(__file__).parent.parent / "lec_bridge.py")

    def can_translate(self, src: Language | str, dst: Language | str) -> bool:
        return self._get_lang(src) in ("ja", "auto") and self._get_lang(dst) == "en"

    def translate(
        self,
        text: str,
        src: Language | str = Language.Japanese,
        dst: Language | str = Language.English,
    ) -> TranslationResult:
        src_code = self._get_lang(src, Language.Japanese)
        dst_code = self._get_lang(dst, Language.English)

        if not text.strip():
            return TranslationResult(self.name, src_code, dst_code, "")
        if src_code not in ("ja", "auto") or dst_code != "en":
            return TranslationResult(
                self.name, src_code, dst_code, "",
                error="LEC Nova supports Japanese to English only",
            )

        py = _find_32bit_python()
        if not py:
            return TranslationResult(
                self.name, src_code, dst_code, "",
                error=(
                    "LEC requires a 32-bit Python (the Nova engine DLL is "
                    "32-bit only). Install one and register it with the 'py' "
                    "launcher (py -3-32), or set TA_ATLAS_32_PYTHON."
                ),
            )
        cmd = [py, "-3-32", self._bridge]
        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except Exception as e:
            return TranslationResult(self.name, src_code, dst_code, "", error=str(e))

        out = proc.stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode == 0 and out:
            return TranslationResult(self.name, src_code, dst_code, out)
        detail = out or proc.stderr.decode("utf-8", errors="replace").strip()[:300]
        return TranslationResult(
            self.name, src_code, dst_code, "",
            error=f"LEC bridge failed: {detail or '(no output)'}",
        )
