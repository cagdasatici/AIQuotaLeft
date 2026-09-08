"""Widget cache writer for WidgetKit desktop widget."""

import json
import os
import subprocess
from datetime import datetime, timezone

from aiquotabar.config import log, WIDGET_HOST_APP, WIDGET_CACHE_DIR, WIDGET_CACHE_FILE
from aiquotabar.providers import LimitRow, UsageData, ProviderData


def _write_widget_cache(
    data: UsageData,
    providers: list[ProviderData],
    cc_stats: dict | None,
    config: dict | None = None,
) -> None:
    """Write current usage snapshot for the WidgetKit widget.

    Writes to ~/Library/Application Support/AIQuotaBar/usage.json
    using atomic replace so the widget never reads a partial file.
    Failures are logged but never crash the main app.
    """
    try:
        def _row_dict(row: LimitRow | None) -> dict | None:
            if row is None:
                return None
            return {"label": row.label, "pct": row.pct, "reset_str": row.reset_str}

        def _active_providers(cfg: dict) -> list[str]:
            """Return list of provider IDs the user has configured."""
            active = []
            if cfg.get("cookie_str"):
                active.append("claude")
            _key_map = {
                "chatgpt_cookies": "chatgpt",
                "copilot_cookies": "copilot",
                "cursor_cookies":  "cursor",
            }
            for cfg_key, prov_id in _key_map.items():
                if cfg.get(cfg_key):
                    active.append(prov_id)
            # Fallback: always show at least Claude
            return active or ["claude"]

        def _bar_providers(cfg: dict) -> list[str] | None:
            """User's explicit bar provider choices (lowercase IDs), or None for auto."""
            chosen = cfg.get("bar_providers")
            if not chosen:
                return None
            return [n.lower() for n in chosen]

        def _copilot_block(provs: list[ProviderData]) -> dict:
            pd = next((p for p in provs if p.name == "Copilot"), None)
            if not pd:
                return {"spent": None, "limit": None, "pct": None, "error": None}
            if pd.error:
                return {"spent": None, "limit": None, "pct": None, "error": pd.error}
            pct = int(round(pd.spent / pd.limit * 100)) if pd.limit else 0
            return {
                "spent": pd.spent,
                "limit": pd.limit,
                "pct": pct,
                "error": None,
            }

        # ChatGPT rows
        chatgpt_pd = next((p for p in providers if p.name == "ChatGPT"), None)
        chatgpt_rows = None
        chatgpt_error = None
        if chatgpt_pd:
            if chatgpt_pd.error:
                chatgpt_error = chatgpt_pd.error
            else:
                raw_rows = getattr(chatgpt_pd, "_rows", None) or []
                chatgpt_rows = [_row_dict(r) for r in raw_rows]

        # Cursor rows
        cursor_pd = next((p for p in providers if p.name == "Cursor"), None)
        cursor_rows = None
        cursor_error = None
        if cursor_pd:
            if cursor_pd.error:
                cursor_error = cursor_pd.error
            else:
                raw_rows = getattr(cursor_pd, "_rows", None) or []
                cursor_rows = [_row_dict(r) for r in raw_rows]

        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "claude": {
                "session": _row_dict(data.session),
                "weekly_all": _row_dict(data.weekly_all),
                "weekly_sonnet": _row_dict(data.weekly_sonnet),
                "overages_enabled": data.overages_enabled,
            },
            "chatgpt": {
                "rows": chatgpt_rows,
                "error": chatgpt_error,
            },
            "cursor": {
                "rows": cursor_rows,
                "error": cursor_error,
            },
            "copilot": _copilot_block(providers),
            "claude_code": {
                "today_messages": (cc_stats or {}).get("today_messages", 0),
                "week_messages": (cc_stats or {}).get("week_messages", 0),
            },
            "active_providers": _active_providers(config or {}),
            "bar_providers": _bar_providers(config or {}),
        }

        os.makedirs(WIDGET_CACHE_DIR, exist_ok=True)
        tmp = os.path.join(WIDGET_CACHE_DIR, ".usage.json.tmp")
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, WIDGET_CACHE_FILE)
        log.debug("widget cache written: %s", WIDGET_CACHE_FILE)

        # The host watches this directory and refreshes the widget when a new
        # file lands, so all that is needed here is for it to be running.
        # (It used to be nudged with `open -a ... --args --reload-widget` after
        # every write. That spawned a process a minute and did nothing useful:
        # --args is only delivered on a cold launch, so once the host was up
        # the nudge just re-activated it and no reload ever happened.)
        ensure_widget_host_running()
    except Exception:
        log.debug("_write_widget_cache failed", exc_info=True)


def _is_widget_installed() -> bool:
    """Check if the AIQuotaBarHost widget app is installed."""
    return os.path.isdir(WIDGET_HOST_APP)


_WIDGET_HOST_PROC = "AIQuotaBarHost.app/Contents/MacOS/AIQuotaBarHost"


def ensure_widget_host_running() -> bool:
    """Start the widget host if it is installed but not running.

    The host watches this cache directory and asks WidgetKit to refresh when a
    new usage.json lands. Without it the widget only updates when macOS feels
    like it, which in practice meant hours of stale numbers. Launched hidden
    and in the background, so it never steals focus.
    """
    if not os.path.isdir(WIDGET_HOST_APP):
        return False
    try:
        already = subprocess.run(
            ["pgrep", "-f", _WIDGET_HOST_PROC],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
        if already:
            return True
        subprocess.Popen(
            ["open", "-g", "-j", "-a", WIDGET_HOST_APP],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log.debug("launched widget host")
        return True
    except Exception as e:
        log.debug("ensure_widget_host_running failed: %s", e)
        return False
