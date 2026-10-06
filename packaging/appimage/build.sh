#!/bin/sh
# Build the Linux AppImage. Run INSIDE a manylinux_2_28 x86_64 container
# with the repository mounted at /src (Qt 6 wheels need glibc >= 2.28):
#
#   docker run --rm -v "$PWD:/src" quay.io/pypa/manylinux_2_28_x86_64 \
#       /src/packaging/appimage/build.sh
#
set -e
PY=/opt/python/cp312-cp312/bin/python
$PY -m venv /tmp/buildvenv
/tmp/buildvenv/bin/pip install --quiet python-appimage
# the recipe bundles the app via local+ (needs it importable here)
/tmp/buildvenv/bin/pip install --quiet -e "/src[gui]" "PyQt6==6.9.1"  # newest with manylinux_2_28 wheels
cd /src/packaging/appimage
/tmp/buildvenv/bin/python-appimage build app . --extra-data /src/dictionaries --python-version 3.12 --linux-tag manylinux_2_28_x86_64
mv *.AppImage /src/dist/ 2>/dev/null || true
ls -la /src/dist/ 2>/dev/null || ls -la ./*.AppImage
