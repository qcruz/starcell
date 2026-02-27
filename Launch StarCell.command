#!/bin/bash
#
# Launch StarCell.command
# Double-click this file in Finder to start the game.
# On first run macOS may ask you to confirm — click Open.
#
cd "$(dirname "$0")"

REPO_DIR="$(pwd)"
LAUNCH_PY="$REPO_DIR/launcher/StarCell.app/Contents/Resources/launch.py"

# ── Find Python 3 ─────────────────────────────────────────────────────────────
PYTHON=""
for candidate in \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
    /usr/bin/python3 \
    "$(command -v python3 2>/dev/null)"; do
    if [ -x "$candidate" ] 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "StarCell requires Python 3.\n\nDownload it from python.org, install it, then try again." buttons {"OK"} default button "OK" with title "StarCell"'
    exit 1
fi

"$PYTHON" "$LAUNCH_PY"
