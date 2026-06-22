#!/usr/bin/env python3
"""
Example Wine bridge for ATLAS.

Place this inside your Wine prefix (or make it available to wine python).

Usage from host:
    wine python atlas_wine_helper.py "日本語の文章" 1

It must be able to import the real ATLAS DLLs (awuenv, atlecont, etc.)
from the ATLAS installation inside Wine.

This is a stub. You need to replicate the actual engine calls that
Shared/Atlas.cpp + exe/TranslationWindows/LocalWindows/AtlasWindow.cpp do.
"""
import sys
import ctypes
from ctypes import c_char_p, c_int, POINTER, c_void_p

def main():
    if len(sys.argv) < 2:
        print("Usage: atlas_wine_helper.py TEXT [DIR=1]")
        return 1
    text = sys.argv[1]
    direction = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # 1=ja->en

    # --- Example of what a real bridge would do ---
    # Load ATLAS DLLs from the Windows ATLAS install inside Wine
    # Then call CreateEngine, TranslatePair, etc.
    #
    # For now we just echo so the GUI shows the path works.
    print(f"[ATLAS via Wine stub] dir={direction} text={text[:80]!r}")
    # Real return would be the translated string.
    # print(translated_text)
    return 0

if __name__ == "__main__":
    sys.exit(main())
