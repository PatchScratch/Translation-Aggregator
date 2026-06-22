"""Cross-platform GUI for Translation Aggregator (Python port)"""
try:
    from .window import MainWindow
except Exception:  # PyQt6 not installed
    MainWindow = None

# Note: we intentionally do NOT import .main here.
# Importing the executable module from the package __init__ can trigger
# the runpy warning: "'translation_aggregator.gui.main' found in sys.modules
# after import of package 'translation_aggregator.gui'".
# Use the console script (transagg-gui) or run directly with:
#   python -m translation_aggregator.gui.main

__all__ = ["MainWindow"]
