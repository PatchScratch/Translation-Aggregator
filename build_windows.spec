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
#   MeCab/unidic - unidic-lite's dictionary data is ~500 MB. The MeCab
#                  pane degrades to "not available" in the exe; JParser
#                  (bundled dictionaries) is the primary parser pane.
#   curl_cffi, pefile - development-time probe tools, not app deps.

from pathlib import Path

ROOT = Path(SPECPATH).resolve()
version = "0.0.0"
for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
    if line.startswith("version"):
        version = line.split("=")[1].strip().strip('"').strip("'")
        break

DATAS = [
    # dictionaries for JParser (edict2 plain + enamdict.gz + conjugations)
    (str(ROOT / "dictionaries" / "edict2"), "dictionaries"),
    (str(ROOT / "dictionaries" / "enamdict.gz"), "dictionaries"),
    (str(ROOT / "dictionaries" / "Conjugations.txt"), "dictionaries"),
    # 32-bit bridge scripts: must be real files next to the frozen modules
    # so an external 32-bit Python can execute them (stdlib-only scripts)
    (str(ROOT / "translation_aggregator" / "atlas_bridge.py"), "translation_aggregator"),
    (str(ROOT / "translation_aggregator" / "lec_bridge.py"), "translation_aggregator"),
]

EXCLUDES = ["playwright", "greenlet", "pyee", "MeCab", "unidic",
            "curl_cffi", "pefile", "pytest"]

gui = Analysis(
    [str(ROOT / "entry_gui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATAS,
    hiddenimports=["translation_aggregator.translators"],
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
