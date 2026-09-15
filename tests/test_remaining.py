"""Regression tests for the two bugs that made this fork misreport quota.

Both were caught by hand and neither was guarded, so both recurred:

1. Percentages are stored as USED and displayed as REMAINING. The first fix
   inverted only the menu bar title, leaving the dropdown showing usage - so
   the title read 88% while the row beneath it read 12% for the same limit.

2. The widget's configuration intent used `default: .none` with an AIProvider
   case named `none`. Swift can resolve that to AIProvider.none instead of
   Optional.none, which turns the optional provider slots into required
   parameters, and WidgetKit then renders a permanently blank widget.
"""
import base64
import json
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch

REPO = pathlib.Path(__file__).resolve().parent.parent
SWIFT = REPO / "AIQuotaBarWidget" / "AIQuotaBarWidgetExtension"


class RemainingConversion(unittest.TestCase):
    def test_inverts_usage(self):
        from aiquotabar.ui import _remaining
        self.assertEqual(_remaining(0), 100)
        self.assertEqual(_remaining(100), 0)
        self.assertEqual(_remaining(12), 88)

    def test_clamps_out_of_range(self):
        from aiquotabar.ui import _remaining
        self.assertEqual(_remaining(120), 0)
        self.assertEqual(_remaining(-20), 100)


class MenuRendering(unittest.TestCase):
    def _row(self, used):
        from aiquotabar.providers import LimitRow
        from aiquotabar.ui import _row_lines
        return _row_lines(LimitRow("Session", used, "resets in 1h"))

    def test_row_reports_remaining_not_used(self):
        line = self._row(12)[0]
        self.assertIn("88%", line)
        self.assertNotIn("12%", line)

    def test_row_is_labelled(self):
        # A bare number is what made the old docs ambiguous.
        self.assertIn("left", self._row(12)[0])

    def test_bar_drains_as_quota_is_consumed(self):
        from aiquotabar.ui import _bar, _remaining
        nearly_full = _bar(_remaining(5)).count("█")
        nearly_empty = _bar(_remaining(95)).count("█")
        self.assertGreater(nearly_full, nearly_empty)

    def test_title_and_dropdown_agree(self):
        # The exact contradiction that shipped: title said one thing, the row
        # under it said another.
        from aiquotabar.ui import _remaining
        used = 17
        self.assertIn(f"{_remaining(used)}%", self._row(used)[0])


class StatusIcon(unittest.TestCase):
    def test_red_when_almost_out(self):
        from aiquotabar.ui import _status_icon
        self.assertEqual(_status_icon(99), "\U0001f534")

    def test_green_when_plenty_left(self):
        from aiquotabar.ui import _status_icon
        self.assertEqual(_status_icon(5), "\U0001f7e2")


class WidgetIntentSchema(unittest.TestCase):
    """Source-level guard; needs no Xcode build."""

    def setUp(self):
        self.src = (SWIFT / "AIProvider.swift").read_text()

    def test_no_none_case(self):
        # `case none` is what makes `default: .none` ambiguous.
        self.assertIn("case claude, chatgpt, cursor", self.src)
        self.assertNotIn("copilot", self.src.lower())

    def test_optional_slots_have_no_ambiguous_default(self):
        self.assertNotIn("default: .none", self.src)

    def test_slots_three_and_four_are_optionals(self):
        self.assertIn("var provider3: AIProvider?", self.src)
        self.assertIn("var provider4: AIProvider?", self.src)


class WidgetViewsShowRemaining(unittest.TestCase):
    def test_views_use_remaining_helpers(self):
        medium = (SWIFT / "MediumWidgetView.swift").read_text()
        small = (SWIFT / "SmallWidgetView.swift").read_text()
        self.assertIn("row.remainingPct", medium)
        self.assertIn("mainRemainingPct", small)

    def test_views_do_not_render_raw_usage(self):
        for name in ("MediumWidgetView.swift", "SmallWidgetView.swift"):
            src = (SWIFT / name).read_text()
            self.assertNotIn("\\(row.pct)%", src, name)
            self.assertNotIn("\\(data.mainPct)%", src, name)


class BuildScript(unittest.TestCase):
    def test_signs_before_installing(self):
        # An unsigned bundle is never registered by macOS.
        sh = (REPO / "AIQuotaBarWidget" / "build_widget.sh").read_text()
        self.assertIn("codesign --force --sign -", sh)
        self.assertIn("--entitlements", sh)

    def test_every_build_gets_a_distinct_version(self):
        # chronod ignores a rebuild at an unchanged bundle version.
        sh = (REPO / "AIQuotaBarWidget" / "build_widget.sh").read_text()
        self.assertIn("CURRENT_PROJECT_VERSION=", sh)
        self.assertIn("BUILD_NUMBER", sh)


class BarPctIgnoresWeeklyRows(unittest.TestCase):
    """Adding the Codex weekly row broke the status bar number: it picked
    max(all rows), so whenever the weekly pct outran the just-reset 5h pct,
    the bar silently displayed the weekly limit instead of the session one
    - the same "session drives the bar, not the max of all limits" rule
    Claude already follows, just not yet applied to multi-row providers."""

    def _pd(self, *label_pcts):
        from aiquotabar.providers import LimitRow, ProviderData
        pd = ProviderData("ChatGPT")
        pd._rows = [LimitRow(label, pct, "") for label, pct in label_pcts]
        return pd

    def test_weekly_row_cannot_outrank_the_5h_row(self):
        from aiquotabar.ui import ClaudeBar
        pd = self._pd(("Codex Tasks", 5), ("Codex Tasks (Weekly)", 90))
        self.assertEqual(ClaudeBar._provider_bar_pct(None, pd), 5)

    def test_falls_back_to_max_when_every_row_is_weekly(self):
        from aiquotabar.ui import ClaudeBar
        pd = self._pd(("Only Weekly", 42))
        self.assertEqual(ClaudeBar._provider_bar_pct(None, pd), 42)

    def test_non_weekly_rows_still_take_the_max_among_themselves(self):
        # Cursor's Auto/API rows are both immediate - unaffected by this fix.
        from aiquotabar.ui import ClaudeBar
        pd = self._pd(("Auto", 30), ("API", 70))
        self.assertEqual(ClaudeBar._provider_bar_pct(None, pd), 70)


class CodexWeeklyLimit(unittest.TestCase):
    """Codex reports a 5h window (primary_window) and a weekly window
    (secondary_window) in every rate-limit bucket; the parser used to read
    only the primary one, so the weekly Codex limit never appeared in the
    menu bar or the widget."""

    @staticmethod
    def _bucket(primary_pct, secondary_pct):
        return {
            "primary_window": {"used_percent": primary_pct, "reset_at": 4102444800},
            "secondary_window": {"used_percent": secondary_pct, "reset_at": 4102444800},
        }

    def test_bucket_yields_both_rows(self):
        from aiquotabar.providers import _parse_wham_bucket
        rows = _parse_wham_bucket(self._bucket(80, 12), "Codex Tasks")
        self.assertEqual([r.label for r in rows], ["Codex Tasks", "Codex Tasks (Weekly)"])
        self.assertEqual([r.pct for r in rows], [80, 12])

    def test_usage_response_surfaces_weekly_row(self):
        from aiquotabar.providers import _parse_wham_usage
        data = {
            "rate_limit": self._bucket(80, 12),
            "code_review_rate_limit": None,
            "additional_rate_limits": None,
        }
        pd = _parse_wham_usage(data)
        self.assertIn("Codex Tasks (Weekly)", [r.label for r in pd._rows])

    def test_missing_secondary_window_is_skipped_not_crashed(self):
        from aiquotabar.providers import _parse_wham_bucket
        rows = _parse_wham_bucket(
            {"primary_window": {"used_percent": 5, "reset_at": 1}}, "Codex Tasks"
        )
        self.assertEqual(len(rows), 1)


class ChatGPTAuth(unittest.TestCase):
    @staticmethod
    def _jwt(claims):
        encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        return f"header.{encoded}.signature"

    def test_extracts_account_id_from_access_token(self):
        from aiquotabar.providers import _chatgpt_account_id
        token = self._jwt({
            "https://api.openai.com/auth": {"chatgpt_account_id": "account-123"},
        })
        self.assertEqual(_chatgpt_account_id({}, token), "account-123")

    def test_detects_expired_access_token_before_usage_request(self):
        from aiquotabar.providers import _chatgpt_token_expired, fetch_chatgpt
        expired = self._jwt({"exp": 1})
        self.assertTrue(_chatgpt_token_expired(expired))
        with patch("aiquotabar.providers._api_get", return_value={"accessToken": expired}) as get, \
                patch("aiquotabar.providers._codex_access_token", return_value=None):
            result = fetch_chatgpt("session=example")
        self.assertIn("access token expired", result.error.lower())
        self.assertEqual(get.call_count, 1)

    def test_expired_browser_token_uses_fresh_matching_codex_token(self):
        from aiquotabar.providers import fetch_chatgpt
        expired = self._jwt({
            "exp": 1,
            "https://api.openai.com/auth": {"chatgpt_account_id": "account-123"},
        })
        fresh = self._jwt({
            "exp": time.time() + 600,
            "https://api.openai.com/auth": {"chatgpt_account_id": "account-123"},
        })
        usage = {"rate_limit": {"primary_window": {"used_percent": 12}}}
        with patch("aiquotabar.providers._api_get", side_effect=[{"accessToken": expired}, usage]) as get, \
                patch("aiquotabar.providers._codex_access_token", return_value=fresh):
            result = fetch_chatgpt("session=example")
        self.assertIsNone(result.error)
        self.assertEqual(get.call_args_list[1].args[1]["Authorization"], f"Bearer {fresh}")

    def test_codex_token_fallback_requires_same_account_and_fresh_token(self):
        from aiquotabar.providers import _codex_access_token
        fresh = self._jwt({"exp": time.time() + 600})
        expired = self._jwt({"exp": 1})
        with tempfile.TemporaryDirectory() as codex_home:
            auth_path = pathlib.Path(codex_home) / "auth.json"
            auth_path.write_text(json.dumps({"tokens": {
                "account_id": "account-123", "access_token": fresh,
            }}))
            with patch.dict("os.environ", {"CODEX_HOME": codex_home}):
                self.assertEqual(_codex_access_token("account-123"), fresh)
                self.assertIsNone(_codex_access_token("another-account"))
                auth_path.write_text(json.dumps({"tokens": {
                    "account_id": "account-123", "access_token": expired,
                }}))
                self.assertIsNone(_codex_access_token("account-123"))

    def test_cookie_detection_prefers_unexpired_browser_session(self):
        from aiquotabar.providers import _auto_detect_chatgpt_cookies
        expired = self._jwt({"exp": 1})
        fresh = self._jwt({"exp": time.time() + 600})
        with patch("aiquotabar.providers._run_cookie_detection", return_value=["session=old", "session=new"]), \
                patch("aiquotabar.providers._chatgpt_session", side_effect=[(expired, "acct"), (fresh, "acct")]):
            self.assertEqual(_auto_detect_chatgpt_cookies(), "session=new")

    def test_fetch_sends_required_account_routing_header(self):
        from aiquotabar.providers import fetch_chatgpt
        token = self._jwt({
            "https://api.openai.com/auth": {"chatgpt_account_id": "account-123"},
        })
        usage = {
            "rate_limit": {
                "primary_window": {"used_percent": 12, "reset_at": 4102444800},
            },
        }
        with patch("aiquotabar.providers._api_get", side_effect=[{"accessToken": token}, usage]) as get:
            result = fetch_chatgpt("session=example")
        self.assertIsNone(result.error)
        self.assertEqual(get.call_args_list[1].args[1]["ChatGPT-Account-Id"], "account-123")


class CopilotRemoval(unittest.TestCase):
    def test_not_registered_or_rendered(self):
        from aiquotabar.providers import PROVIDER_REGISTRY, COOKIE_PROVIDERS
        self.assertNotIn("copilot_cookies", PROVIDER_REGISTRY)
        self.assertNotIn("copilot_cookies", COOKIE_PROVIDERS)
        providers = (REPO / "aiquotabar" / "providers.py").read_text().lower()
        ui = (REPO / "aiquotabar" / "ui.py").read_text().lower()
        widget = (REPO / "aiquotabar" / "widget.py").read_text().lower()
        self.assertNotIn("fetch_copilot", providers)
        self.assertNotIn("github copilot", ui)
        self.assertNotIn("copilot.png", ui)
        self.assertNotIn("copilot", widget)


if __name__ == "__main__":
    unittest.main()
