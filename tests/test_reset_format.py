"""Regression tests for reset-time formatting.

Two bugs fixed together:

1. Under-20h resets rendered as a relative countdown ("resets in 4h 12m"),
   inconsistent with the weekly cap's absolute "resets Mon 18:59" - and a
   countdown goes stale the moment it's read. Cursor built its own separate
   "resets in Nd Nh" string and never went through the shared formatter at
   all, so unifying the threshold alone would not have fixed it.

2. The shared formatter never converted the API's UTC timestamp to local
   time before formatting, so the printed clock time was silently wrong by
   the local UTC offset - not merely relative, wrong. A UTC+2 reader saw a
   21:00 reset labeled 19:00.
"""
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from aiquotabar.providers import _fmt_reset  # noqa: E402


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


class AlwaysAbsolute(unittest.TestCase):
    """Every horizon must render a clock time, never a countdown."""

    def test_short_horizon_is_not_relative(self):
        out = _fmt_reset(_iso(timedelta(minutes=40)))
        self.assertNotIn("in ", out)
        self.assertNotRegex(out, r"\d+h\s*\d*m?$")

    def test_claude_session_horizon_is_not_relative(self):
        out = _fmt_reset(_iso(timedelta(hours=4, minutes=12)))
        self.assertNotIn("in ", out)

    def test_monthly_horizon_is_not_relative(self):
        # Cursor's billing cycle: the case that had its own separate,
        # never-unified "resets in Nd Nh" string.
        out = _fmt_reset(_iso(timedelta(days=27)))
        self.assertNotIn("in ", out)

    def test_past_reads_as_soon_not_a_negative_countdown(self):
        self.assertEqual(_fmt_reset(_iso(timedelta(minutes=-5))), "resets soon")


class LocalTimezone(unittest.TestCase):
    """The printed clock time must be local, not a mislabeled UTC value."""

    def test_matches_local_wall_clock(self):
        target = datetime.now(timezone.utc) + timedelta(hours=3)
        out = _fmt_reset(target.isoformat())
        expected_hhmm = target.astimezone().strftime("%H:%M")
        self.assertIn(expected_hhmm, out)

    def test_does_not_leak_the_utc_clock_time(self):
        # Only meaningful off UTC (this machine is UTC+2); skip if not.
        offset = datetime.now().astimezone().utcoffset()
        if offset is None or offset.total_seconds() == 0:
            self.skipTest("host is UTC; the bug this guards is invisible here")
        target = datetime.now(timezone.utc) + timedelta(hours=3)
        out = _fmt_reset(target.isoformat())
        utc_hhmm = target.strftime("%H:%M")
        self.assertNotIn(utc_hhmm, out)

    def test_weekday_reflects_local_date_across_midnight(self):
        # A UTC time just before midnight that rolls to the next local day
        # must report the LOCAL weekday, not the UTC one.
        now_utc = datetime.now(timezone.utc)
        near_midnight_utc = now_utc.replace(hour=23, minute=30, second=0, microsecond=0)
        if near_midnight_utc <= now_utc:
            near_midnight_utc += timedelta(days=1)
        out = _fmt_reset(near_midnight_utc.isoformat())
        expected_day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
            near_midnight_utc.astimezone().weekday()
        ]
        self.assertIn(expected_day, out)


class Disambiguation(unittest.TestCase):
    def test_within_a_week_shows_weekday_only(self):
        out = _fmt_reset(_iso(timedelta(days=2)))
        self.assertNotRegex(out, r"[A-Z][a-z]{2} \d{1,2},")

    def test_beyond_a_week_shows_a_calendar_date(self):
        # A bare weekday this far out is ambiguous - which Wednesday?
        out = _fmt_reset(_iso(timedelta(days=27)))
        self.assertRegex(out, r"[A-Z][a-z]{2} \d{1,2},")


class CursorUsesSharedFormatter(unittest.TestCase):
    def test_no_hand_rolled_relative_string_left_in_source(self):
        src = (REPO / "aiquotabar" / "providers.py").read_text()
        self.assertNotIn('f"resets in {days}d {hours}h"', src)
        self.assertNotIn('f"resets in {hours}h"', src)

    def test_cursor_reset_is_built_from_fmt_reset(self):
        src = (REPO / "aiquotabar" / "providers.py").read_text()
        self.assertIn('reset_str = _fmt_reset(data.get("billingCycleEnd"))', src)


if __name__ == "__main__":
    unittest.main()
