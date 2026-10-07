# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Translation Aggregator (Windows release build).
#
# Produces in dist/:
#   TranslationAggregator.exe   (GUI, windowed)
#   transagg.exe                (CLI, console)
# The 32-bit bridge scripts land beside the frozen modules so an
# external 32-bit Python can execute them for the ATLAS/LEC engines.
#
# Build:  pyinstaller build_windows.spec
#
# Deliberately excluded:
#   playwright   - the optional Baidu engine; bundling Chromium's driver
#                  would bloat the exe enormously. The engine reports a
#                  clear "install playwright" error if selected.
#   MeCab/unidic - the optional MeCab pane; the dictionary is ~300 MB on
#                  disk. Users install it via Tools > Install MeCab, which
#                  pip-installs the fugashi wheel into the per-user extras
#                  dir and downloads/unpacks the unidic-lite dicdir there
#                  (loaded through sys.path at startup).
#   curl_cffi, pefile - development-time probe tools, not app deps.

from pathlib import Path

ROOT = Path(SPECPATH).resolve()
version = "0.0.0"
for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
    if line.startswith("version"):
        version = line.split("=")[1].strip().strip('"').strip("'")
        break

DATAS = [
    # window/taskbar icon, loaded at runtime by gui/main.py (the embedded
    # exe icon only covers Explorer); .ico for Windows, .png for AppImage/dev
    (str(ROOT / "assets" / "icon.ico"), "assets"),
    (str(ROOT / "assets" / "icon.png"), "assets"),
    # dictionaries for JParser (edict2 plain + enamdict.gz + conjugations)
    (str(ROOT / "dictionaries" / "edict2"), "dictionaries"),
    (str(ROOT / "dictionaries" / "enamdict.gz"), "dictionaries"),
    (str(ROOT / "dictionaries" / "Conjugations.txt"), "dictionaries"),
    # 32-bit bridge scripts: must be real files next to the frozen modules
    # so an external 32-bit Python can execute them (stdlib-only scripts)
    (str(ROOT / "translation_aggregator" / "atlas_bridge.py"), "translation_aggregator"),
    (str(ROOT / "translation_aggregator" / "lec_bridge.py"), "translation_aggregator"),
]

# pip must ship as REAL FILES on disk (datas), not inside the PYZ archive:
# its vendored distlib locates its own resources through the import system
# and cannot find them inside the frozen archive. The in-app "Install MeCab"
# tool runs pip in-process (there is no python.exe to spawn). GUI exe only.
# Keep _PIP_STDLIB in sync with pip's imports (scan pip's source for
# `from/import <stdlib>` when bumping the build image's pip).
_pip_pkg = Path(__import__("pip").__file__).resolve().parent
# dist-info NEXT TO the pip package (importlib.metadata may resolve a
# different environment's pip and hand back its whole site-packages dir)
_pip_dist = next(_pip_pkg.parent.glob("pip-*.dist-info"), None)
DATAS += [(str(_pip_pkg), "pip")]
if _pip_dist is not None:
    DATAS += [(str(_pip_dist), _pip_dist.name)]

_PIP_STDLIB = [
    "abc", "argparse", "array", "ast", "atexit", "base64", "binascii",
    "bisect", "bz2", "calendar", "codecs", "collections", "colorsys",
    "compileall", "compression", "configparser", "contextlib", "copy",
    "csv", "ctypes", "dataclasses", "datetime", "decimal", "difflib",
    "email", "enum", "fnmatch", "fractions", "functools", "getpass",
    "glob", "graphlib", "hashlib", "hmac", "html", "http", "importlib",
    "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "linecache", "locale", "logging", "lzma", "math", "mimetypes",
    "mmap", "netrc", "operator", "optparse", "os", "pathlib", "pickle",
    "pkgutil", "platform", "plistlib", "pty", "py_compile", "queue",
    "random", "re", "reprlib", "runpy", "select", "shlex", "shutil",
    "site", "socket", "ssl", "stat", "string", "struct", "subprocess",
    "sysconfig", "tarfile", "tempfile", "textwrap", "threading", "time",
    "tokenize", "tomllib", "traceback", "types", "typing", "unicodedata",
    "urllib", "uuid", "venv", "warnings", "weakref", "winreg", "xmlrpc",
    "zipfile", "zlib",
    "collections.abc", "ctypes.util", "ctypes.wintypes",
    "email.errors", "email.header", "email.message", "email.parser",
    "email.policy", "email.utils", "encodings.idna", "html.entities",
    "html.parser", "http.client", "http.cookiejar", "http.cookies",
    "importlib.abc", "importlib.machinery", "importlib.metadata",
    "importlib.resources", "importlib.util", "logging.config",
    "logging.handlers", "urllib.error", "urllib.parse",
    "urllib.request", "xmlrpc.client",
]

EXCLUDES = ["playwright", "greenlet", "pyee", "MeCab", "unidic",
            "unidic_lite", "ipadic", "fugashi", "pip",
            "curl_cffi", "pefile", "pytest"]

gui = Analysis(
    [str(ROOT / "entry_gui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATAS,
    hiddenimports=["translation_aggregator.translators"] + _PIP_STDLIB,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz_gui = PYZ(gui.pure)
exe_gui = EXE(
    pyz_gui,
    gui.scripts,
    gui.binaries,
    gui.datas,
    [],
    name="TranslationAggregator",
    console=False,
    disable_windowed_traceback=False,
    upx=False,
    icon=str(ROOT / "assets" / "icon.ico"),
)

cli = Analysis(
    [str(ROOT / "entry_cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 32-bit bridge scripts for the local engines (see DATAS above)
        (str(ROOT / "translation_aggregator" / "atlas_bridge.py"), "translation_aggregator"),
        (str(ROOT / "translation_aggregator" / "lec_bridge.py"), "translation_aggregator"),
    ],
    hiddenimports=["translation_aggregator.translators"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz_cli = PYZ(cli.pure)
exe_cli = EXE(
    pyz_cli,
    cli.scripts,
    cli.binaries,
    cli.datas,
    [],
    name="transagg",
    console=True,
    disable_windowed_traceback=False,
    upx=False,
)
