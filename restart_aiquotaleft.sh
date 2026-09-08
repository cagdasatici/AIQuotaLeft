#!/bin/bash
# Stop every running AIQuotaLeft menu bar instance, then start exactly one.
#
# The menu bar app runs as a LaunchAgent, so there is nothing in /Applications
# to click, and AIQuotaBarHost.app is the widget host (LSUIElement) rather than
# the app itself. This script is what the Dock launcher runs.
LABEL="com.claudebar"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
APP_DIR="$HOME/.ai-quota-bar"
PATTERN="ai-quota-bar/claude_bar.py"
UID_NUM=$(id -u)

running() { pgrep -f "$PATTERN" 2>/dev/null; }

# 1. Graceful stop: SIGTERM so rumps can remove its status item, SIGKILL for
#    anything still alive after ~5s.
pids=$(running || true)
if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    for _ in $(seq 1 20); do
        sleep 0.25
        [ -z "$(running || true)" ] && break
    done
    leftover=$(running || true)
    [ -n "$leftover" ] && kill -9 $leftover 2>/dev/null || true
fi

# 2. Start one, under launchd so it stays supervised.
if ! launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
    [ -f "$PLIST" ] && launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>/dev/null || true
fi
launchctl kickstart -k "gui/$UID_NUM/$LABEL" 2>/dev/null || true

# 3. Verify; fall back to a direct launch if launchd could not start it.
for _ in $(seq 1 20); do
    sleep 0.5
    [ -n "$(running || true)" ] && break
done
if [ -z "$(running || true)" ] && [ -x "$APP_DIR/.venv/bin/python3" ]; then
    nohup "$APP_DIR/.venv/bin/python3" "$APP_DIR/claude_bar.py" \
        >>"$HOME/.claude_bar.log" 2>&1 &
    sleep 3
fi

[ -n "$(running || true)" ] || { echo "Could not start - see ~/.claude_bar.log" >&2; exit 1; }
echo "AIQuotaLeft restarted"
