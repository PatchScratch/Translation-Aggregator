#!/usr/bin/env python
"""
atlas_bridge.py

Small standalone 32-bit Python script that loads the real 32-bit ATLAS V14 (or V13)
DLLs and performs translation.

This is the bridge used by the 64-bit main process to talk to the 32-bit ATLAS engine.

It is intentionally self-contained so it can be executed with a 32-bit Python interpreter
(py -3-32, python-32.exe, etc.).

Protocol:
  - Read one line from stdin: the source text (UTF-8)
  - Optional environment variables or command line:
      ATLAS_ENV=General
      ATLAS_DIRECTION=1   (1=ja->en, 2=en->ja)
  - Write one line to stdout: the translated text (or empty on error)
  - On error, write nothing or the error prefixed with "ERROR:" (the caller treats non-empty stderr or empty output as failure)

Exit code 0 on success (even if translation is empty).
"""
from __future__ import annotations

import os
import sys
import platform
import ctypes
from ctypes import c_char_p, POINTER, c_void_p, c_uint, byref, c_int

# ---------------------------------------------------------------------------
# Configuration (can be overridden by environment)
# ---------------------------------------------------------------------------
ATLAS_ENV = os.environ.get("ATLAS_ENV", "General")
ATLAS_DIRECTION = int(os.environ.get("ATLAS_DIRECTION", "1"))  # 1=ja->en, 2=en->ja

# ---------------------------------------------------------------------------
# Find the ATLAS installation (same spirit as the main engine)
# ---------------------------------------------------------------------------
def find_atlas_dir() -> str | None:
    # 1. Hard-coded known good path (user confirmed this exact install)
    for p in (
        r"C:\Program Files (x86)\ATLAS V14",
        r"C:\Program Files\ATLAS V14",
    ):
        if os.path.isdir(p):
            print(f"[atlas_bridge] Found ATLAS dir (hardcoded): {p}", file=sys.stderr)
            return p

    # 2. Registry (original TA method)
    try:
        import winreg
        for v in (14, 13):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Fujitsu\ATLAS\V{v}.0\EJ")
                val, _ = winreg.QueryValueEx(key, "TRENV EJ")
                winreg.CloseKey(key)
                if isinstance(val, str) and val:
                    d = os.path.dirname(val)
                    if os.path.isdir(d):
                        print(f"[atlas_bridge] Found ATLAS dir (registry): {d}", file=sys.stderr)
                        return d
            except Exception:
                pass
    except Exception:
        pass

    # 3. Broad scan of Program Files
    for base in (r"C:\Program Files", r"C:\Program Files (x86)"):
        if not os.path.isdir(base):
            continue
        try:
            for name in os.listdir(base):
                if "atlas" not in name.lower():
                    continue
                d = os.path.join(base, name)
                if os.path.isdir(d):
                    try:
                        files = {f.lower() for f in os.listdir(d)}
                        if any("atlecont" in f or "awuenv" in f for f in files):
                            print(f"[atlas_bridge] Found ATLAS dir (scan): {d}", file=sys.stderr)
                            return d
                    except Exception:
                        pass
        except Exception:
            pass

    print("[atlas_bridge] ATLAS directory NOT FOUND", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Core loading + translation
# ---------------------------------------------------------------------------
class _AtlasBridge:
    def __init__(self):
        self.atle = None
        self.free = None
        self.translate_pair = None
        self.create_engine = None
        self.atl_init = None
        self.set_state = None
        self.ready = False
        self.last_err = None

    def load(self) -> bool:
        install = find_atlas_dir()
        if not install:
            self.last_err = "Failed to initialize Fujitsu ATLAS v14. (ATLAS directory not found)"
            return False

        print(f"[atlas_bridge] Using ATLAS dir: {install}", file=sys.stderr)

        try:
            # Make DLLs discoverable (very important on Windows)
            try:
                os.add_dll_directory(install)
            except Exception:
                pass
            try:
                if install not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = install + ";" + os.environ.get("PATH", "")
            except Exception:
                pass

            def load_any(name_lower: str):
                for f in os.listdir(install):
                    if f.lower() == name_lower:
                        full = os.path.join(install, f)
                        print(f"[atlas_bridge] Loading {full}", file=sys.stderr)
                        try:
                            dll = ctypes.CDLL(full)
                            return dll
                        except Exception as e:
                            self.last_err = f"Failed to load {f}: {e}"
                            print(f"[atlas_bridge] ERROR loading {f}: {e}", file=sys.stderr)
                            return None
                return None

            atle = load_any("atlecont.dll")
            if not atle:
                self.last_err = "Failed to initialize Fujitsu ATLAS v14. (AtleCont.dll not loadable)"
                return False

            self.atle = atle

            # Resolve symbols
            for sym in ("CreateEngine", "DestroyEngine", "TranslatePair",
                        "FreeAtlasData", "AtlInitEngineData", "SetTransState"):
                try:
                    fn = getattr(atle, sym)
                    setattr(self, sym.lower().replace("atlinitenginedata", "atl_init"), fn)
                    print(f"[atlas_bridge] Resolved {sym}", file=sys.stderr)
                except Exception:
                    print(f"[atlas_bridge] MISSING symbol: {sym}", file=sys.stderr)

            self.translate_pair = getattr(self, "translatepair", None) or getattr(atle, "TranslatePair", None)
            self.free = getattr(self, "freeatlasdata", None) or getattr(atle, "FreeAtlasData", None)
            self.create_engine = getattr(self, "createengine", None) or getattr(atle, "CreateEngine", None)
            self.atl_init = getattr(self, "atl_init", None) or getattr(atle, "AtlInitEngineData", None)
            self.set_state = getattr(self, "settransstate", None) or getattr(atle, "SetTransState", None)

            if not self.translate_pair:
                self.last_err = "Failed to initialize Fujitsu ATLAS v14. (TranslatePair not found)"
                print("[atlas_bridge] ERROR: TranslatePair not found", file=sys.stderr)
                return False

            # === Exact initialization sequence from original TA (Shared/Atlas.cpp) ===
            # 1. AtlInitEngineData(0, 2, ..., 0, ...)
            # 2. CreateEngine(1, direction, 0, env)   <--- first arg MUST be 1
            # Check that CreateEngine returns 1

            # AtlInitEngineData
            if self.atl_init:
                try:
                    d1 = c_int(0)
                    d2 = c_int(0)
                    ret = self.atl_init(0, 2, byref(d1), 0, byref(d2))
                    print(f"[atlas_bridge] AtlInitEngineData(0,2,...) returned {ret}", file=sys.stderr)
                except Exception as e:
                    print(f"[atlas_bridge] AtlInitEngineData crashed: {e}", file=sys.stderr)

            if self.set_state:
                try:
                    self.set_state(0)
                except Exception as e:
                    print(f"[atlas_bridge] SetTransState non-fatal: {e}", file=sys.stderr)

            # CreateEngine - CRITICAL: first arg = 1, second = direction
            create_ret = None
            if self.create_engine:
                env = (ATLAS_ENV or "General").encode("shift_jis", errors="replace")
                try:
                    create_ret = self.create_engine(1, c_int(ATLAS_DIRECTION), 0, env)
                    print(f"[atlas_bridge] CreateEngine(1, dir, 0, env) returned {create_ret}", file=sys.stderr)
                except Exception as e:
                    print(f"[atlas_bridge] CreateEngine(1, dir, 0, env) CRASHED: {e}", file=sys.stderr)
                    create_ret = -999

            if create_ret == 1:
                self.ready = True
                self.last_err = None
                print("[atlas_bridge] CreateEngine succeeded (returned 1). Engine is ready.", file=sys.stderr)
            else:
                self.ready = False
                if not self.last_err:
                    self.last_err = f"Failed to initialize Fujitsu ATLAS v14. (CreateEngine returned {create_ret})"
                print("[atlas_bridge] CreateEngine did NOT return 1. Engine is NOT ready.", file=sys.stderr)

            return True

        except Exception as e:
            self.last_err = f"Failed to initialize Fujitsu ATLAS v14. ({e})"
            print(f"[atlas_bridge] FATAL: {e}", file=sys.stderr)
            return False

    def translate(self, text: str) -> str:
        if not self.ready or not self.translate_pair:
            return ""

        try:
            jis = text.encode("shift_jis", errors="replace")
            out_ptr = c_char_p()
            dummy = c_void_p()
            size = c_uint(0)

            res = self.translate_pair(jis, byref(out_ptr), byref(dummy), byref(size))
            if res == 0 and out_ptr.value:
                result = out_ptr.value.decode("shift_jis", errors="replace")
                if self.free:
                    try:
                        self.free(out_ptr.value, None, None, None)
                    except Exception:
                        pass
                return result
        except Exception:
            pass
        return ""


def main() -> int:
    # Always print diagnostics first
    print(f"[atlas_bridge] Bridge process: {sys.executable}", file=sys.stderr)
    print(f"[atlas_bridge] Bridge arch: {platform.architecture()}", file=sys.stderr)

    # CRITICAL: the bridge itself must be 32-bit
    is_32 = (platform.architecture()[0] == '32bit') or (sys.maxsize <= 2**32)
    if not is_32:
        print("ERROR: This bridge is running under 64-bit Python. ATLAS V14 DLLs are 32-bit only.", file=sys.stderr)
        print("Failed to initialize Fujitsu ATLAS v14. (bridge is 64-bit)", file=sys.stderr)
        print("", end="")
        return 1

    # Read source text from stdin
    try:
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    except Exception:
        text = ""

    bridge = _AtlasBridge()
    if not bridge.load():
        print("", end="")
        if bridge.last_err:
            print(bridge.last_err, file=sys.stderr)
        else:
            print("Failed to initialize Fujitsu ATLAS v14. (bridge could not load ATLAS DLLs)", file=sys.stderr)
        return 1

    if not text:
        print("", end="")
        return 0

    out = bridge.translate(text)
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
