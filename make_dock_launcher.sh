#!/bin/bash
# Build "Restart AIQuotaLeft.app" for the Dock.
#
# Built with osacompile rather than hand-rolled: an app bundle whose main
# executable is a shell script fails to launch on macOS 26 with LaunchServices
# error -10669. osacompile produces a bundle with a real Mach-O executable.
set -e
APP_NAME="Restart AIQuotaLeft"
DEST="${1:-/Applications}"
APP="$DEST/$APP_NAME.app"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SRC_DIR/restart_aiquotaleft.sh"

mkdir -p "$DEST"; rm -rf "$APP"
osacompile -o "$APP" -e "do shell script \"'$SCRIPT'\"" \
    -e 'display notification "Restarted - look for the ◆ in your menu bar" with title "AIQuotaLeft"'

# Icon (skipped silently if the tools are unavailable)
ICON_SRC="$SRC_DIR/assets/claude_icon.png"
if [ -f "$ICON_SRC" ] && command -v sips >/dev/null && command -v iconutil >/dev/null; then
    TMP=$(mktemp -d); ICONSET="$TMP/icon.iconset"; mkdir -p "$ICONSET"
    for sz in 16 32 128 256 512; do
        sips -z $sz $sz "$ICON_SRC" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null 2>&1 || true
        sips -z $((sz*2)) $((sz*2)) "$ICON_SRC" --out "$ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null 2>&1 || true
    done
    iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns" >/dev/null 2>&1 || true
    rm -rf "$TMP"
fi
echo "  Built: $APP"
