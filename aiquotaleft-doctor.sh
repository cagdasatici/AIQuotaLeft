#!/bin/bash
# AIQuotaLeft doctor - verify every invariant, repair what it can.
#
# Both moving parts are supervised by launchd and must simply always be up:
#   com.claudebar              the menu bar app; fetches quota, writes usage.json
#   com.aiquotaleft.widgethost the widget host; watches usage.json, refreshes
#                              the widget. Without it the widget goes stale.
#
# Everything here is idempotent: run it as often as you like.
# Usage: aiquotaleft-doctor.sh [--check]     (--check reports without repairing)

CHECK_ONLY=false
[ "$1" = "--check" ] && CHECK_ONLY=true

APP_DIR="$HOME/.ai-quota-bar"
AGENTS="$HOME/Library/LaunchAgents"
BAR_LABEL="com.claudebar"
HOST_LABEL="com.aiquotaleft.widgethost"
HOST_APP="/Applications/AIQuotaBarHost.app"
HOST_BIN="$HOST_APP/Contents/MacOS/AIQuotaBarHost"
CACHE="$HOME/Library/Application Support/AIQuotaBar/usage.json"
UID_NUM=$(id -u)
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

# Match on the executable path (ps comm), never on the command line: pgrep -f
# also matches this script and its own greps, since they mention these paths.
host_pids()  { ps -Ao pid=,comm= | awk -v p="$HOST_BIN" '$2 == p {print $1}'; }
host_strays(){ ps -Ao pid=,comm= | awk -v p="$HOST_BIN" '$2 ~ /AIQuotaBarHost$/ && $2 != p {print $1}'; }
bar_pids()   { ps -Ao pid=,args= | awk '/[c]laude_bar\.py/ {print $1}'; }

ok=0; fixed=0; failed=0
say_ok()     { printf '  \033[32m✓\033[0m %s\n' "$1"; ok=$((ok+1)); }
say_fixed()  { printf '  \033[33m⟳\033[0m %s\n' "$1"; fixed=$((fixed+1)); }
say_failed() { printf '  \033[31m✗\033[0m %s\n' "$1"; failed=$((failed+1)); }
repairing()  { [ "$CHECK_ONLY" = false ]; }

echo ""
echo "  AIQuotaLeft doctor"
echo "  ──────────────────"

# ── 1. launchd plists ────────────────────────────────────────────────────────
write_bar_plist() {
    cat > "$AGENTS/$BAR_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$BAR_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$APP_DIR/.venv/bin/python3</string>
        <string>$APP_DIR/claude_bar.py</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$HOME/.claude_bar.log</string>
    <key>StandardErrorPath</key><string>$HOME/.claude_bar.log</string>
</dict>
</plist>
PLIST
}

write_host_plist() {
    cat > "$AGENTS/$HOST_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$HOST_LABEL</string>
    <key>ProgramArguments</key><array><string>$HOST_BIN</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardErrorPath</key><string>$HOME/.aiquotaleft_widgethost.log</string>
</dict>
</plist>
PLIST
}

# The menu bar agent must restart on ANY exit. It shipped with
# KeepAlive={SuccessfulExit:false}, which restarts only after a crash - so a
# clean exit left it dead until the next login.
if [ ! -f "$AGENTS/$BAR_LABEL.plist" ] || \
   ! plutil -extract KeepAlive xml1 -o - "$AGENTS/$BAR_LABEL.plist" 2>/dev/null | grep -q "<true/>"; then
    if repairing; then
        write_bar_plist
        launchctl bootout "gui/$UID_NUM/$BAR_LABEL" 2>/dev/null
        launchctl bootstrap "gui/$UID_NUM" "$AGENTS/$BAR_LABEL.plist" 2>/dev/null
        say_fixed "menu bar agent: now restarts on any exit"
    else
        say_failed "menu bar agent: only restarts after a crash"
    fi
else
    say_ok "menu bar agent supervised (KeepAlive)"
fi

# The widget host was never supervised at all - it relied on the menu bar app
# happening to launch it.
if [ -d "$HOST_APP" ]; then
    if [ ! -f "$AGENTS/$HOST_LABEL.plist" ]; then
        if repairing; then
            write_host_plist
            launchctl bootstrap "gui/$UID_NUM" "$AGENTS/$HOST_LABEL.plist" 2>/dev/null
            say_fixed "widget host agent: created and loaded"
        else
            say_failed "widget host agent: missing (widget will go stale)"
        fi
    else
        say_ok "widget host agent present"
    fi
fi

# The watchdog. KeepAlive alone proved unreliable here: launchd reported
# "pended nondemand spawn" and left the job dead for minutes after a SIGTERM,
# despite KeepAlive=true. A timer job is demand-spawned and dependable, so
# recovery is bounded at WATCHDOG_INTERVAL rather than left to launchd's mood.
WATCHDOG_LABEL="com.aiquotaleft.doctor"
WATCHDOG_INTERVAL=120
write_watchdog_plist() {
    cat > "$AGENTS/$WATCHDOG_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$WATCHDOG_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$APP_DIR/aiquotaleft-doctor.sh</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>StartInterval</key><integer>$WATCHDOG_INTERVAL</integer>
    <key>StandardOutPath</key><string>$HOME/.aiquotaleft_doctor.log</string>
    <key>StandardErrorPath</key><string>$HOME/.aiquotaleft_doctor.log</string>
</dict>
</plist>
PLIST
}

if [ "$SELF_IS_WATCHDOG" != "1" ]; then
    if [ ! -f "$AGENTS/$WATCHDOG_LABEL.plist" ]; then
        if repairing; then
            write_watchdog_plist
            launchctl bootstrap "gui/$UID_NUM" "$AGENTS/$WATCHDOG_LABEL.plist" 2>/dev/null
            say_fixed "watchdog installed (checks every ${WATCHDOG_INTERVAL}s)"
        else
            say_failed "watchdog not installed"
        fi
    elif launchctl print "gui/$UID_NUM/$WATCHDOG_LABEL" >/dev/null 2>&1; then
        say_ok "watchdog active (every ${WATCHDOG_INTERVAL}s)"
    elif repairing; then
        launchctl bootstrap "gui/$UID_NUM" "$AGENTS/$WATCHDOG_LABEL.plist" 2>/dev/null
        say_fixed "watchdog reloaded"
    else
        say_failed "watchdog not loaded"
    fi
fi

# Cron watchdog. On this machine launchd would not perform automatic spawns
# for these jobs - RunAtLoad, KeepAlive and StartInterval all sat at
# "pended nondemand spawn" with runs=0, and only an explicit kickstart
# started anything. cron is a separate mechanism and fires regardless, so
# recovery does not depend on launchd behaving.
CRON_LINE="*/2 * * * * /bin/bash $APP_DIR/aiquotaleft-doctor.sh >> $HOME/.aiquotaleft_doctor.log 2>&1"
if crontab -l 2>/dev/null | grep -q "aiquotaleft-doctor.sh"; then
    say_ok "cron watchdog installed (every 2 min)"
elif repairing; then
    ( crontab -l 2>/dev/null | grep -v "aiquotaleft-doctor.sh"; echo "$CRON_LINE" ) | crontab -
    say_fixed "cron watchdog installed (every 2 min)"
else
    say_failed "cron watchdog missing"
fi

# ── 2. agents actually loaded ────────────────────────────────────────────────
for label in "$BAR_LABEL" "$HOST_LABEL"; do
    [ -f "$AGENTS/$label.plist" ] || continue
    if launchctl print "gui/$UID_NUM/$label" >/dev/null 2>&1; then
        say_ok "$label loaded"
    elif repairing; then
        launchctl bootstrap "gui/$UID_NUM" "$AGENTS/$label.plist" 2>/dev/null
        say_fixed "$label bootstrapped"
    else
        say_failed "$label not loaded"
    fi
done

# ── 3. no processes from stale locations ─────────────────────────────────────
# Copies in build dirs, DerivedData and /tmp share the bundle id. One ran from
# a build directory for three days, serving old code while /Applications
# looked correct.
strays=$(host_strays)
if [ -n "$strays" ]; then
    if repairing; then
        echo "$strays" | xargs kill 2>/dev/null
        say_fixed "killed host process(es) running from outside /Applications"
    else
        say_failed "host running from outside /Applications"
    fi
else
    say_ok "no host processes from stale locations"
fi

# ── 4. exactly one menu bar instance ─────────────────────────────────────────
pids=$(bar_pids)
count=$(printf '%s' "$pids" | grep -c . )
managed=$(launchctl list "$BAR_LABEL" 2>/dev/null | awk -F'= ' '/"PID"/{gsub(/;/,"",$2);print $2}')
if [ "$count" -gt 1 ]; then
    if repairing; then
        for p in $pids; do [ "$p" != "$managed" ] && kill "$p" 2>/dev/null; done
        say_fixed "killed duplicate menu bar instance(s)"
    else
        say_failed "$count menu bar instances running"
    fi
elif [ "$count" -eq 1 ]; then
    say_ok "exactly one menu bar instance"
else
    if repairing; then
        launchctl kickstart -k "gui/$UID_NUM/$BAR_LABEL" 2>/dev/null
        say_fixed "menu bar app was not running - started"
    else
        say_failed "menu bar app not running"
    fi
fi

# ── 5. widget host up (the widget's freshness depends on it) ─────────────────
if [ -d "$HOST_APP" ]; then
    if [ -n "$(host_pids)" ]; then
        say_ok "widget host running (widget refreshes on new data)"
    elif repairing; then
        launchctl kickstart -k "gui/$UID_NUM/$HOST_LABEL" 2>/dev/null
        sleep 2
        [ -n "$(host_pids)" ] && say_fixed "widget host started" \
                               || say_failed "widget host would not start"
    else
        say_failed "widget host not running - widget will show stale data"
    fi
fi

# ── 6. no duplicate bundle registrations ─────────────────────────────────────
dupes=$("$LSREGISTER" -dump 2>/dev/null | grep "path:" | grep -i "AIQuotaBarHost.app" \
        | sed 's/^ *path: *//' | sed 's/ (.*//' | grep -v "^$HOST_APP" | sort -u)
if [ -n "$dupes" ]; then
    if repairing; then
        echo "$dupes" | while read -r d; do [ -n "$d" ] && "$LSREGISTER" -u "$d" 2>/dev/null; done
        "$LSREGISTER" -f "$HOST_APP" 2>/dev/null
        say_fixed "unregistered duplicate bundle copies"
    else
        say_failed "duplicate bundle copies registered"
    fi
else
    say_ok "only /Applications registered"
fi

# ── 7. widget bundle signed (unsigned never registers) ───────────────────────
if [ -d "$HOST_APP" ]; then
    if codesign --verify --deep --strict "$HOST_APP" 2>/dev/null; then
        say_ok "widget bundle signature valid"
    else
        say_failed "widget signature invalid - rerun AIQuotaBarWidget/build_widget.sh"
    fi
fi

# ── 8. data actually fresh ───────────────────────────────────────────────────
if [ -f "$CACHE" ]; then
    age=$(( $(date +%s) - $(stat -f %m "$CACHE") ))
    if [ "$age" -lt 600 ]; then
        say_ok "usage data fresh (${age}s old)"
    elif repairing; then
        launchctl kickstart -k "gui/$UID_NUM/$BAR_LABEL" 2>/dev/null
        say_fixed "usage data was ${age}s stale - restarted menu bar app"
    else
        say_failed "usage data ${age}s stale"
    fi
else
    say_failed "no usage.json yet"
fi

echo ""
echo "  $ok ok, $fixed repaired, $failed failed"
echo ""
[ "$failed" -eq 0 ]
