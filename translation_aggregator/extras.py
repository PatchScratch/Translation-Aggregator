"""Optional-component install target for portable builds (MeCab, Playwright…).

Frozen builds cannot pip-install into themselves: the single-file exe extracts
to a fresh temp folder per run and the AppImage squashfs is read-only. Heavy
optional components are instead installed once into a per-user "extras"
directory next to the config file via `pip install --target`, and that
directory is put on sys.path at startup.

The Windows exe embeds no python.exe to run pip as a subprocess, so pip runs
in-process there (bundled via collect_all("pip") in build_windows.spec); the
AppImage's embedded interpreter and dev environments use a normal
`python -m pip` subprocess.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .config import config


def extras_dir() -> Path:
    """Per-user install target for optional components; stable across app reinstalls."""
    return Path(config.path).parent / "extras"


def ensure_on_sys_path() -> None:
    d = extras_dir()
    if d.is_dir():
        p = str(d)
        if p not in sys.path:
            sys.path.insert(0, p)


def is_frozen_exe() -> bool:
    return bool(getattr(sys, "frozen", False))


def pip_install(args: List[str]) -> Tuple[bool, str]:
    """Run pip with the given args; returns (ok, last output line).

    In the frozen exe there is no interpreter, so pip's in-process entry point
    is used; everywhere else a `python -m pip` subprocess.
    """
    full = [*args, "--disable-pip-version-check"]
    if is_frozen_exe():
        try:
            from pip._internal.cli.main import main as pip_main  # type: ignore
        except ImportError as e:
            return False, f"pip is not bundled with this build ({e})"
        rc = pip_main(full)
        return rc == 0, ("done" if rc == 0 else f"pip exited with code {rc}")
    cmd = [sys.executable, "-m", "pip", *full]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except Exception as e:
        return False, str(e)
    last = ""
    for chunk in ((proc.stdout or "") + "\n" + (proc.stderr or "")).splitlines():
        line = chunk.strip()
        if line:
            last = line
    return proc.returncode == 0, last


# --- MeCab dictionary (unidic-lite ships only an sdist, so pip cannot install
# it inside the frozen exe — it would need to build with sys.executable, which
# is the app itself there. The sdist's dicdir is pre-built data, so we fetch
# the tarball and unpack it ourselves; that works identically everywhere.)

_DICT_PKG = "unidic-lite"


def _sdist_url() -> Optional[str]:
    """Download URL of the newest unidic-lite sdist, via the PyPI JSON API."""
    try:
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{_DICT_PKG}/json", timeout=30
        ) as r:
            urls = json.load(r)["urls"]
        for u in urls:
            if u["packagetype"] == "sdist":
                return u["url"]
    except Exception:
        pass
    return None


def install_mecab_dict(progress: Callable[[str], None] = lambda _s: None) -> Tuple[bool, str]:
    """Download the unidic-lite sdist and unpack its pre-built dicdir into extras.

    Returns (ok, summary). progress receives human-readable status lines.
    """
    import gzip
    import shutil

    url = _sdist_url()
    if not url:
        return False, "could not resolve the dictionary download URL (pypi.org reachable?)"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            buf = io.BytesIO()
            done = 0
            last_mb = -1
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                buf.write(chunk)
                done += len(chunk)
                mb = int(done / 1e6)
                if total and mb != last_mb:
                    last_mb = mb
                    progress(f"downloading dictionary… {mb} / {total/1e6:.0f} MB")
        progress("download complete; unpacking…")

        target = extras_dir() / "unidic_lite"
        staging = extras_dir() / "_unidic_staging"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

        def _extract(t, members, dest):
            try:
                t.extractall(dest, members=members, filter="data")
            except TypeError:  # python without the filter= parameter
                t.extractall(dest, members=members)

        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(buf.getvalue())), mode="r:") as t:
            dic_members = [
                m for m in t.getmembers()
                if "/unidic_lite/dicdir/" in m.name
                or m.name.rstrip("/").endswith("/unidic_lite/dicdir")
            ]
            _extract(t, dic_members, staging)
            # the tarball prefixes everything with '<pkg>-<ver>/'; find the package dir
            pkg_dir = next((p for p in staging.glob("*/unidic_lite") if p.is_dir()), None)
            if pkg_dir is None or not (pkg_dir / "dicdir" / "sys.dic").exists():
                shutil.rmtree(staging, ignore_errors=True)
                return False, "dictionary archive did not contain unidic_lite/dicdir/sys.dic"
            # make it a real package: fugashi/mecab-python3 auto-detection does
            # `import unidic_lite; unidic_lite.DICDIR` — a bare data directory
            # would import as a namespace package without DICDIR and crash them
            (pkg_dir / "__init__.py").write_text(
                '"""unidic-lite dictionary data installed by Translation Aggregator '
                '(dicdir unpacked from the sdist)."""\n'
                "import os\n\n"
                'DICDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dicdir")\n',
                encoding="utf-8",
            )
            if "LICENSE.unidic" in t.getnames():
                lic = t.getmember("LICENSE.unidic")
                (pkg_dir / "LICENSE.unidic").write_bytes(t.extractfile(lic).read())

        if target.exists():
            shutil.rmtree(target)
        os.replace(pkg_dir, target)
        shutil.rmtree(staging, ignore_errors=True)
        return True, "dictionary ready at " + str(target / "dicdir")
    except Exception as e:
        return False, f"dictionary install failed: {e}"
