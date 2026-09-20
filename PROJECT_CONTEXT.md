# AIQuotaLeft — current context

This is a navigation snapshot, not a replacement for requirements or live evidence. Update it after a meaningful milestone; keep history in existing records.

## Snapshot — 2026-09-20

HEAD `559ca3e`, with existing `scratch.md` preserved. **42 tests passed** using the installed Python 3.12 environment. Default macOS Python 3.9 lacks rumps and cannot parse/evaluate the module's union-type usage; that failed attempt is an environment mismatch, not a passing app check. No GUI, Keychain, live provider, install, or Xcode build was exercised.

Cursor support has now been removed from the menu bar, panel, widget payload/configuration, and provider registry. Claude and Codex usage rows are named `5-hour` and `Weekly` (with Claude's optional `Weekly (Sonnet)` row). The floating menu renders each row's own compact absolute reset timestamp beneath its label in legible secondary text; when Claude has not started a 5-hour window, it truthfully says `starts on use`. **44 tests pass** using the installed Python 3.12 environment; `git diff --check` also passes.

Remaining-focused menu/widget, reset formatting, ChatGPT auth fixes and vanished-icon recovery exist. Runtime provider/session compatibility and fresh-install/widget validation remain the key acceptance work. Growth/adoption was not measured.

## Read only for the relevant task

| Task | Entry points / authority |
|---|---|
| Current product/attribution | `README.md`, especially “Changes in this fork” |
| UI/conversion | `aiquotabar/ui.py`, `tests/test_remaining.py` |
| Providers/reset/auth | `aiquotabar/providers.py`, `tests/test_reset_format.py`; fixtures only unless live checks requested |
| Widget | `AIQuotaBarWidget/`; Python source assertions do not replace an Xcode/runtime check |
| Installation/recovery | `install.sh`, `aiquotaleft-doctor.sh`, `restart_aiquotaleft.sh` |
| Historical growth strategy | `docs/AGENT_GUIDANCE_HISTORY.md`, `docs/planning/`; opt in for distribution tasks only |

Next useful delivery: a reproducible clean-install + sleep/wake + icon recovery + widget matrix. Keep this fork's reliability goal ahead of inherited star-chasing tasks unless the owner requests distribution work. Never interpret stale percentage data as current quota.
