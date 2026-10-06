"""PyInstaller entry point for the GUI (relative imports need a top-level launcher)."""
from translation_aggregator.gui.main import main

if __name__ == "__main__":
    main()
