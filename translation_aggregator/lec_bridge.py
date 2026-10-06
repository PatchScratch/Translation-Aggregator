"""32-bit bridge for the LEC Nova engine (Power Translator 15).

The engine DLL Nova\\JaEn\\EngineDll_je.dll is 32-bit and one-way
(Japanese -> English). Protocol: UTF-8 source on stdin, UTF-8 result on
stdout, diagnostics on stderr. Same shape as atlas_bridge.py.

API (from the original TA LECWindow.cpp):
  eg_init2(<Nova\\JaEn dir>, 0) -> 0 on success
  eg_translate_multi(0, src_cp932, bufsize, dst) -> 0 on success
  eg_end()
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import c_int, create_string_buffer

CODEPAGE = "cp932"

# The direct engine mangles these full-width brackets/punctuation; the
# original TA replaced them before translating.
_CHAR_FIXES = str.maketrans({
    "「": "[", "｢": "[", "」": "]", "｣": "]",
    "≪": "(", "（": "(", "≫": ")", "）": ")", "…": " ", "：": "￤",
})


def _log(msg: str):
    print(f"[lec_bridge] {msg}", file=sys.stderr)


def find_engine():
    """Return (dll_path, init_dir) for the installed LEC Nova JaEn engine."""
    # explicit override first
    base = os.environ.get("TA_LEC_DIR", "")
    candidates = []
    if base:
        candidates.append(base)
    # registry (original TA method): ApplicationPath points into the
    # Applications folder; the engine root is its parent
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\LogoMedia\LEC Power Translator 15\Configuration",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
        )
        val, _ = winreg.QueryValueEx(key, "ApplicationPath")
        winreg.CloseKey(key)
        p = os.path.dirname(val.rstrip("\\/"))
        if os.path.isdir(p):
            candidates.append(p)
    except Exception:
        pass
    candidates.append(r"C:\Program Files (x86)\Power Translator 15")

    for base in candidates:
        init_dir = os.path.join(base, "Nova", "JaEn")
        dll = os.path.join(init_dir, "EngineDll_je.dll")
        if os.path.isfile(dll):
            return dll, init_dir
    return None, None


def main() -> int:
    if sys.maxsize > 2**32:
        _log("ERROR: bridge is 64-bit; LEC Nova is 32-bit only")
        return 1

    try:
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    except Exception:
        text = ""
    if not text:
        return 0

    dll_path, init_dir = find_engine()
    if not dll_path:
        _log("LEC Nova engine not found (Power Translator 15 \\ Nova\\JaEn)")
        print("LEC engine not found. Install Power Translator or set TA_LEC_DIR.", end="")
        return 1

    try:
        dll = ctypes.CDLL(dll_path)
    except Exception as e:
        _log(f"failed to load {dll_path}: {e}")
        return 1

    try:
        init2 = getattr(dll, "eg_init2", None)
        init = getattr(dll, "eg_init", None)
        if init2 is not None:
            init2.restype = c_int
            ok = init2(init_dir.encode(CODEPAGE), 0) == 0
        elif init is not None:
            init.restype = c_int
            ok = init(init_dir.encode(CODEPAGE)) == 0
        else:
            ok = False
        if not ok:
            _log("eg_init2 failed")
            print("LEC engine failed to initialize.", end="")
            return 1

        src = text.translate(_CHAR_FIXES).encode(CODEPAGE, errors="replace")
        translate = dll.eg_translate_multi
        translate.restype = c_int

        # the API gives no required-size query: start big, grow if filled
        size = len(src) * 4 + 0x100
        result = ""
        for _ in range(4):
            buf = create_string_buffer(size)
            res = translate(0, src, size, buf)
            out = buf.value.decode(CODEPAGE, errors="replace")
            if res == 0 and len(out) + 1 < size:
                result = out
                break
            size *= 2
        try:
            dll.eg_end()
        except Exception:
            pass
        sys.stdout.buffer.write(result.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
        return 0
    except Exception as e:
        _log(f"translate failed: {type(e).__name__} {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
