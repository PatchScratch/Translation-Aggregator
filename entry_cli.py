"""PyInstaller entry point for the CLI (relative imports need a top-level launcher)."""
import sys

from translation_aggregator.cli import main

if __name__ == "__main__":
    sys.exit(main())
