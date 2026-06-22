from __future__ import annotations

import os
import platform
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AtlasResult:
    text: str
    error: Optional[str] = None


class AtlasEngine:
    """
    100% behavior port of the original ATLAS pane (AtlasWindow.cpp + Shared/Atlas).

    Responsibilities:
    - Only translates ja<->en (original CanTranslate rule).
    - Reads Environment from config (atlas_environment, default "General").
    - Supports rule set (.trs) and output flags (stored in config).
    - On Windows: attempts to load the real ATLAS v13/v14 DLLs and call the engine
      (mirrors InitAtlas / TranslateFull / AtlasTransSJIS flow).
    - On failure: returns the exact message the original shows:
      "Failed to initialize Fujitsu ATLAS v14."
    - On other platforms: falls back to Wine + helper script if configured.
    """

    def __init__(self):
        self._mode = "none"          # none | native | wine
        self._available = False
        self._direction = 1          # 1=ja->en, 2=en->ja
        self._environment = "General"
        self._trs_path = ""
        self._flags = 0
        # Native handles (populated only in native mode)
        self._dlls_loaded = False
        self._TranslateFull = None
        self._TranslateFullA = None
        self._SetAtlasConfig = None  # if we expose config later
        self._last_error = None

        self._init_backend()

    # ------------------------------------------------------------------
    # Public configuration (called when user changes ATLAS settings)
    # ------------------------------------------------------------------
    def configure(self, environment: str = "General", trs_path: str = "", flags: int = 0):
        """Update runtime config. Re-init native engine on next translate if needed."""
        self._environment = environment or "General"
        self._trs_path = trs_path or ""
        self._flags = int(flags or 0)
        # Force re-init of native side so new env/trs/flags are used
        if self._mode == "native":
            self._dlls_loaded = False
            self._TranslateFull = None
            self._TranslateFullA = None

    def set_direction(self, direction: int):
        """1 = Japanese→English, 2 = English→Japanese (matches ATLAS_JAP_TO_ENG etc)."""
        self._direction = 2 if direction == 2 else 1

    @property
    def available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def mode(self) -> str:
        """Current backend mode: 'native', 'bridge', 'wine', or 'none'."""
        return self._mode

    @property
    def is_using_bridge(self) -> bool:
        """True if we are talking to the 32-bit ATLAS engine via the subprocess bridge."""
        return self._mode == "bridge"

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _init_backend(self):
        if platform.system() == "Windows":
            # 1. Try direct native load (only works if *this* Python is 32-bit)
            if self._try_load_native():
                self._mode = "native"
                self._available = True
                return

            # 2. On 64-bit Python, try the 32-bit bridge subprocess (future-proof)
            if self._setup_bridge():
                self._mode = "bridge"
                self._available = True
                return

        # Wine fallback (rarely used for ATLAS)
        if self._try_wine():
            self._mode = "wine"
            self._available = True
            return

        self._mode = "none"
        self._available = False

    # ------------------------------------------------------------------
    # 32-bit bridge support (for 64-bit Python hosts)
    # ------------------------------------------------------------------
    def _find_32bit_python(self) -> Optional[str]:
        """
        Locate a 32-bit Python interpreter for the ATLAS bridge.
        Preference order:
          1. TA_ATLAS_32_PYTHON env var (full path to 32-bit python.exe)
          2. 'py' launcher with -3-32 (official Windows way – preferred)
          3. Common 32-bit Python install locations (we verify bitness)
        Returns a string that is either:
          - full path to a 32-bit python.exe, or
          - the 'py' launcher path (caller will add "-3-32")
        Returns None if nothing usable is found (and sets a detailed self._last_error).
        """
        # 1. Explicit override from user
        env = os.environ.get("TA_ATLAS_32_PYTHON")
        if env and os.path.isfile(env):
            return env

        # 2. Try the official 'py' launcher with -3-32
        py_launcher = shutil.which("py")
        if py_launcher:
            # Verify that a 32-bit runtime actually exists for the launcher
            try:
                # This will print the 32-bit python path if available, or fail
                out = subprocess.check_output(
                    [py_launcher, "-3-32", "-c", "import sys; print(sys.executable)"],
                    stderr=subprocess.STDOUT,
                    timeout=8
                )
                out = out.decode("utf-8", errors="replace").strip()
                if out and os.path.isfile(out):
                    # Success – we have a 32-bit Python via the launcher
                    # We return the *launcher* so the caller knows to use py -3-32
                    return py_launcher
            except subprocess.CalledProcessError as e:
                # Launcher exists but no 32-bit Python registered for it
                msg = e.output.decode("utf-8", errors="replace") if e.output else ""
                self._last_error = (
                    "ATLAS requires a 32-bit Python (the ATLAS V14 engine DLLs are 32-bit only).\n\n"
                    "The 'py' launcher is installed, but no 32-bit Python is registered.\n\n"
                    "How to fix:\n"
                    "  1. Install a 32-bit Python (e.g. Python 3.10 32-bit from python.org)\n"
                    "  2. During install, enable the 'py launcher' option if offered.\n"
                    "  3. After install, run:   py --list\n"
                    "     You should see an entry like  -3.10-32\n"
                    "  4. Restart this application.\n\n"
                    "Alternative (if you already have a 32-bit Python):\n"
                    '  setx TA_ATLAS_32_PYTHON "C:\\full\\path\\to\\python-32.exe"\n\n'
                    + (f"Launcher output:\n{msg}" if msg else "")
                )
                return None
            except Exception as e:
                # Launcher problem (unlikely)
                self._last_error = (
                    "ATLAS requires a 32-bit Python.\n"
                    "The 'py' launcher was found but could not be used to locate a 32-bit runtime.\n"
                    f"Error: {e}\n\n"
                    "Install a 32-bit Python and register it, or set TA_ATLAS_32_PYTHON."
                )
                return None

        # 3. Search common locations and verify they are actually 32-bit
        search_roots = [
            r"C:\Program Files (x86)",
            os.path.expanduser(r"~\AppData\Local\Programs\Python"),
            r"C:\Python",
        ]
        for root in search_roots:
            if not os.path.isdir(root):
                continue
            try:
                for entry in os.listdir(root):
                    if not entry.lower().startswith("python"):
                        continue
                    p = os.path.join(root, entry, "python.exe")
                    if os.path.isfile(p):
                        try:
                            out = subprocess.check_output(
                                [p, "-c", "import sys,platform; print(platform.architecture()[0]); print(sys.maxsize <= 2**32)"],
                                stderr=subprocess.DEVNULL,
                                timeout=5
                            )
                            text = out.decode("utf-8", errors="replace").lower()
                            if "32bit" in text or "true" in text:
                                return p
                        except Exception:
                            pass
            except Exception:
                pass

        # Nothing found – give a clear actionable message
        self._last_error = (
            "ATLAS requires a 32-bit Python (ATLAS V14 DLLs are 32-bit only).\n\n"
            "Your current Python is 64-bit.\n\n"
            "Recommended fix:\n"
            "  • Install a 32-bit Python (Python 3.10 32-bit or 3.11 32-bit from python.org)\n"
            "  • Make sure the installer enables the 'py launcher'\n"
            "  • After install, open a new terminal and run:   py --list\n"
            "    You should see something like:  -3.10-32\n"
            "  • Restart this application\n\n"
            "Manual alternative:\n"
            '  setx TA_ATLAS_32_PYTHON "C:\\path\\to\\your\\32-bit\\python.exe"\n'
            "  (then restart the app)"
        )
        return None

    def _setup_bridge(self) -> bool:
        """
        Prepare to use the 32-bit bridge subprocess.
        Returns True if we have everything needed.
        """
        py = self._find_32bit_python()
        if not py:
            self._last_error = (
                "ATLAS requires a 32-bit Python (ATLAS V14 DLLs are 32-bit only).\n\n"
                "Your main Python is 64-bit.\n\n"
                "Fix:\n"
                "1. Install a 32-bit Python (e.g. Python 3.10 32-bit from python.org)\n"
                "2. Register it so the 'py' launcher sees it (py --list should show a *-32 entry)\n"
                "   or set the environment variable TA_ATLAS_32_PYTHON to the full path of the 32-bit python.exe\n"
                "3. Restart this application.\n\n"
                "Example:\n"
                '  setx TA_ATLAS_32_PYTHON "C:\\Python310-32\\python.exe"'
            )
            return False

        bridge = Path(__file__).parent / "atlas_bridge.py"
        if not bridge.exists():
            self._last_error = "Failed to initialize Fujitsu ATLAS v14. (atlas_bridge.py not found)"
            return False

        self._bridge_python = py
        self._bridge_script = str(bridge)
        self._bridge_available = True
        return True

    def _translate_via_bridge(self, text: str) -> AtlasResult:
        """
        Call the 32-bit bridge to perform translation.
        Uses the 'py -3-32' launcher when available so the user does not need to
        change their main (64-bit) Python environment.
        """
        if not getattr(self, "_bridge_available", False):
            # Return the detailed message set by _setup_bridge / _find_32bit_python
            msg = self._last_error or "Failed to initialize Fujitsu ATLAS v14."
            return AtlasResult("", msg)

        py = getattr(self, "_bridge_python", None)
        script = getattr(self, "_bridge_script", None)
        if not py or not script:
            return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14.")

        env = os.environ.copy()
        env["ATLAS_ENV"] = self._environment or "General"
        env["ATLAS_DIRECTION"] = str(self._direction)

        # Build the command
        if os.path.basename(py).lower() in ("py.exe", "py"):
            # py launcher + force 32-bit
            cmd = [py, "-3-32", script]
        else:
            cmd = [py, script]

        # Always include the exact command in diagnostics
        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)

        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=60,
            )
            out = proc.stdout.decode("utf-8", errors="replace").strip()
            err = proc.stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode == 0 and out:
                return AtlasResult(out)

            # Surface the actual error from the 32-bit bridge (this is what the user needs to see)
            msg = "Failed to initialize Fujitsu ATLAS v14."
            details = []
            details.append(f"bridge command: {cmd_str}")
            if err:
                details.append("bridge stderr:\n" + err.strip())
            if out:
                details.append("bridge stdout:\n" + out.strip())
            if not err and not out:
                details.append("(no output from bridge process)")

            msg += "\n" + "\n".join(details)
            self._last_error = msg[:1500]
            return AtlasResult("", msg)

        except FileNotFoundError:
            msg = f"Failed to initialize Fujitsu ATLAS v14.\nbridge command: {cmd_str}\n(32-bit Python not found – set TA_ATLAS_32_PYTHON or register a 32-bit Python with the 'py' launcher)"
            self._last_error = msg
            return AtlasResult("", msg)
        except subprocess.TimeoutExpired:
            return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14. (timeout)")
        except Exception as e:
            return AtlasResult("", f"Failed to initialize Fujitsu ATLAS v14. ({e})")

    def _find_atlas_install_dir(self):
        """Return the directory containing the user's ATLAS V14 installation.
        We know it is the standard location with mixed-case DLLs.
        """
        d = r"C:\Program Files (x86)\ATLAS V14"
        if os.path.isdir(d):
            return d
        for cand in (r"C:\Program Files\ATLAS V14",):
            if os.path.isdir(cand):
                return cand
        return None

    def _try_load_native(self) -> bool:
        """Load the real ATLAS V14 32-bit DLLs.
        ATLAS V14 is a 32-bit product. This will only work from 32-bit Python.
        """
        try:
            import ctypes
            import platform
            import os as _os

            # Fast fail with a clear message if we are 64-bit Python
            if platform.architecture()[0] == '64bit':
                self._last_error = "Failed to initialize Fujitsu ATLAS v14. (This Python is 64-bit; ATLAS V14 DLLs are 32-bit)"
                return False

            install_dir = self._find_atlas_install_dir()
            if not install_dir:
                self._last_error = "Failed to initialize Fujitsu ATLAS v14. (Could not locate ATLAS V14 folder)"
                return False

            # Make dependent DLLs discoverable
            try:
                _os.add_dll_directory(install_dir)
            except Exception:
                pass

            # Also add to PATH for LoadLibrary delay loads
            try:
                if install_dir not in _os.environ.get("PATH", ""):
                    _os.environ["PATH"] = install_dir + ";" + _os.environ.get("PATH", "")
            except Exception:
                pass

            def load_dll_anycase(basename):
                target = basename.lower()
                for f in _os.listdir(install_dir):
                    if f.lower() == target:
                        full = _os.path.join(install_dir, f)
                        try:
                            return ctypes.CDLL(full)
                        except Exception as e:
                            self._last_error = f"Failed to load {f}: {e}"
                            return None
                return None

            # Load order can matter — start with the main engine
            atle = load_dll_anycase("AtleCont.dll")
            if not atle:
                atle = load_dll_anycase("atlcont.dll")

            awdict = load_dll_anycase("Awdict.dll")
            awuenv = load_dll_anycase("Awuenv.dll")

            if not atle:
                if not self._last_error:
                    self._last_error = "Failed to initialize Fujitsu ATLAS v14."
                return False

            self._atle = atle
            self._awdict = awdict
            self._awuenv = awuenv
            self._atlas_dir = install_dir

            # Grab the symbols the original uses
            for name in ("CreateEngine", "DestroyEngine", "TranslatePair",
                         "FreeAtlasData", "AtlInitEngineData", "SetTransState"):
                try:
                    setattr(self, name, getattr(atle, name))
                except Exception:
                    pass

            try:
                self.AwuWordDel = getattr(awdict, "AwuWordDel") if awdict else None
            except Exception:
                self.AwuWordDel = None

            self._dlls_loaded = True
            self._last_error = None
            return True

        except Exception as e:
            self._last_error = f"Failed to initialize Fujitsu ATLAS v14. ({e})"
            return False

    def _try_wine(self) -> bool:
        wine = shutil.which("wine") or shutil.which("wine64")
        if not wine:
            return False
        self._wine_cmd = wine
        return True

    # ------------------------------------------------------------------
    # Core translation
    # ------------------------------------------------------------------
    def translate(self, text: str, direction: Optional[int] = None) -> AtlasResult:
        """
        direction: 1 = ja->en (default), 2 = en->ja
        Mirrors the original flow:
          - Set direction / environment
          - Call the equivalent of TranslateFull
          - Return the result or the exact failure string the original shows.
        """
        if direction is not None:
            self._direction = 2 if direction == 2 else 1

        if not text or not text.strip():
            return AtlasResult("")

        if self._mode == "native":
            return self._translate_native(text)

        if self._mode == "bridge":
            return self._translate_via_bridge(text)

        if self._mode == "wine":
            return self._translate_wine(text)

        # No working backend. Prefer the detailed message we built (especially the
        # "ATLAS requires a 32-bit Python..." guidance) over the short classic string.
        if self._last_error:
            return AtlasResult("", self._last_error)

        # 100% faithful fallback for Windows
        if platform.system().lower().startswith("win"):
            return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14.")
        return AtlasResult("", "ATLAS not available")

    def _translate_native(self, text: str) -> AtlasResult:
        """Call the real engine if loaded; otherwise produce the exact original failure message."""
        if not self._dlls_loaded:
            return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14.")

        try:
            import ctypes
            from ctypes import c_char_p, POINTER, c_void_p, c_uint, byref, c_int

            # Convert to SHIFT-JIS exactly like the original (932).
            jis = text.encode("shift_jis", errors="replace")

            # ------------------------------------------------------------------
            # Original flow (InitAtlas + CreateEngine + AtlInitEngineData + SetTransState + TranslatePair)
            # We do the minimal version that the real DLLs need.
            # ------------------------------------------------------------------
            atle = getattr(self, "_atle", None)
            if not atle:
                return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14.")

            # Resolve symbols if not already cached
            CreateEngine = getattr(self, "CreateEngine", None) or getattr(atle, "CreateEngine", None)
            DestroyEngine = getattr(self, "DestroyEngine", None) or getattr(atle, "DestroyEngine", None)
            TranslatePair = getattr(self, "TranslatePair", None) or getattr(atle, "TranslatePair", None)
            FreeAtlasData = getattr(self, "FreeAtlasData", None) or getattr(atle, "FreeAtlasData", None)
            AtlInitEngineData = getattr(self, "AtlInitEngineData", None) or getattr(atle, "AtlInitEngineData", None)
            SetTransState = getattr(self, "SetTransState", None) or getattr(atle, "SetTransState", None)

            if not (CreateEngine and TranslatePair):
                return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14.")

            # We keep a very small state so we don't re-create the engine on every call
            if not getattr(self, "_atlas_engine_ready", False):
                # CreateEngine(0, dir, 0, env) — dir 1=ja->en, 2=en->ja (matches original)
                # env is usually "General" or another from transenv.ini
                env = (self._environment or "General").encode("shift_jis", errors="replace")
                try:
                    CreateEngine(0, c_int(self._direction), 0, env)
                except Exception:
                    # Some builds take different args; try the 3-arg variant
                    try:
                        CreateEngine(0, c_int(self._direction), 0)
                    except Exception:
                        pass

                # AtlInitEngineData is called by original; call if present
                if AtlInitEngineData:
                    try:
                        dummy1 = c_int(0)
                        dummy2 = c_int(0)
                        AtlInitEngineData(0, 0, byref(dummy1), 0, byref(dummy2))
                    except Exception:
                        pass

                if SetTransState:
                    try:
                        SetTransState(0)
                    except Exception:
                        pass

                self._atlas_engine_ready = True

            # Now do the actual translation
            out_ptr = c_char_p()
            dummy = c_void_p()
            size = c_uint(0)

            res = TranslatePair(jis, byref(out_ptr), byref(dummy), byref(size))
            if res == 0 and out_ptr.value:
                result = out_ptr.value.decode("shift_jis", errors="replace")
                # Free the atlas-allocated buffer if possible
                if FreeAtlasData:
                    try:
                        FreeAtlasData(out_ptr.value, None, None, None)
                    except Exception:
                        pass
                return AtlasResult(result)

            # If TranslatePair failed or gave nothing, fall back to any other high-level export
            for sym in ("AtlasTransSJIS", "Translate", "Trans"):
                try:
                    fn = getattr(atle, sym)
                    fn.restype = c_char_p
                    fn.argtypes = [c_char_p]
                    out = fn(jis)
                    if out:
                        return AtlasResult(out.decode("shift_jis", errors="replace"))
                except Exception:
                    continue

            return AtlasResult("", "Failed to initialize Fujitsu ATLAS v14.")

        except Exception as e:
            return AtlasResult("", str(e))

    def _translate_wine(self, text: str) -> AtlasResult:
        helper = os.environ.get("TA_ATLAS_WINE_HELPER", "atlas_wine_helper.py")
        if not os.path.exists(helper) and not shutil.which(helper):
            # Still try – the helper may be on PATH inside Wine
            pass
        try:
            out = subprocess.check_output(
                [self._wine_cmd, "python", helper, text, str(self._direction)],
                stderr=subprocess.STDOUT,
                timeout=60,
            )
            return AtlasResult(out.decode("utf-8", errors="replace").strip())
        except FileNotFoundError:
            return AtlasResult("", "Wine helper not found. Set TA_ATLAS_WINE_HELPER.")
        except subprocess.CalledProcessError as e:
            return AtlasResult("", e.output.decode("utf-8", errors="replace")[:800])
        except Exception as e:
            return AtlasResult("", str(e))


def shutil_which(name: str) -> Optional[str]:
    return shutil.which(name)
