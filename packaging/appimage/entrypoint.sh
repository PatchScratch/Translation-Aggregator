#!/bin/sh
# AppRun entry point. `--cli` runs the command line tool instead of the GUI.
if [ "$1" = "--cli" ]; then
	shift
	exec {{ python-executable }} -sE -m translation_aggregator.cli "$@"
fi
exec {{ python-executable }} -sE -m translation_aggregator.gui.main "$@"
