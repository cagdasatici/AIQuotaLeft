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
import ast
import pathlib
import unittest

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
        self.assertNotIn("case claude, chatgpt, cursor, copilot, none", self.src)

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


class CopilotProvider(unittest.TestCase):
    def test_fetch_copilot_exists(self):
        # It was deleted by a stray edit, leaving its body orphaned inside
        # fetch_glm as unreachable code.
        tree = ast.parse((REPO / "aiquotabar" / "providers.py").read_text())
        names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        self.assertIn("fetch_copilot", names)

    def test_registered(self):
        from aiquotabar.providers import PROVIDER_REGISTRY, COOKIE_PROVIDERS
        self.assertIn("copilot_cookies", PROVIDER_REGISTRY)
        self.assertIn("copilot_cookies", COOKIE_PROVIDERS)


if __name__ == "__main__":
    unittest.main()
