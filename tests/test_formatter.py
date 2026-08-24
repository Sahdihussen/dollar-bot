import json
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from output.formatter import format_market_board, day_rate_stats


def make_snapshot(**overrides):
    snap = {
        "city": "erbil",
        "market_layer": "bourse",
        "consensus_rate": 152900,
        "median_rate": 152900,
        "min_rate": 152850,
        "max_rate": 152950,
        "spread": 100,
        "buy_rate": 152850,
        "sell_rate": 152950,
        "observation_count": 10,
        "source_count": 2,
        "freshest_at": "2026-08-24T13:00:00+00:00",
        "category_rates": json.dumps({}),
        "snapshot_at": "2026-08-24T13:00:00+00:00",
    }
    snap.update(overrides)
    return snap


def board_patches(**kw):
    """Standard DB mocks for format_market_board: no metals, no source link, no day history."""
    defaults = {
        "get_recent_by_product": [],
        "get_setting": "off",
        "get_rate_history_all": [],
    }
    defaults.update(kw)
    return defaults


class patched_board:
    """Context manager patching each DB helper named in patch_kwargs."""

    def __init__(self, patch_kwargs):
        self.patch_kwargs = patch_kwargs

    def __enter__(self):
        self._stack = ExitStack()
        for name, value in self.patch_kwargs.items():
            self._stack.enter_context(
                patch(f"output.formatter.db.{name}", return_value=value)
            )
        return self

    def __exit__(self, *exc):
        self._stack.__exit__(*exc)


class TestFormatMarketBoard(unittest.TestCase):
    def test_renders_city_rates_and_summary(self):
        with patched_board(board_patches()):
            board = format_market_board([make_snapshot()])

        self.assertIn("هەولێر", board)          # Kurdish city name
        self.assertIn("152,900", board)          # consensus rate formatted
        self.assertIn("152,850 — 152,950", board)  # buy — sell spread
        self.assertIn("Source: 10 market observations", board)

    def test_buy_sell_line_requires_both(self):
        snap = make_snapshot(buy_rate=152850, sell_rate=None)
        with patched_board(board_patches()):
            board = format_market_board([snap])
        self.assertIn("152,900", board)
        self.assertNotIn("152,850 —", board)

    def test_category_lines_suppress_consensus_line(self):
        snap = make_snapshot(category_rates=json.dumps({"5000_IQD_CATEGORY": 152900}))
        with patched_board(board_patches()):
            board = format_market_board([snap])
        self.assertIn("پێنجی: 152,900", board)
        # Category breakdown present -> no generic consensus line
        self.assertNotIn("📊 152,850 — 152,950", board)

    def test_metals_block_shown_when_observations_exist(self):
        lira = {"rate": 958, "rate_role": "BUY"}
        silver = {"rate": 2186, "rate_role": "SELL"}
        with patched_board(board_patches(get_recent_by_product=[lira, silver])):
            board = format_market_board([make_snapshot()])
        self.assertIn("دوبەی لیرا", board)
        self.assertIn("958$ (كڕین)", board)
        self.assertIn("زیو (کیلۆ)", board)
        self.assertIn("2,186$ (فرۆشتن)", board)

    def test_metals_block_hidden_when_no_data(self):
        with patched_board(board_patches()):
            board = format_market_board([make_snapshot()])
        self.assertNotIn("زیو", board)
        self.assertNotIn("دوبەی", board)

    def test_source_link_only_when_setting_on(self):
        obs = [{"source": "iraqborsa", "created_at": "2026-08-24T13:00:00+00:00"}]
        with patched_board(board_patches(get_setting="on", get_recent_observations=obs)):
            board = format_market_board([make_snapshot()])
        self.assertIn("Source: t.me/iraqborsa", board)

        with patched_board(board_patches(get_setting="off", get_recent_observations=obs)):
            board = format_market_board([make_snapshot()])
        self.assertNotIn("t.me/iraqborsa", board)

    def test_empty_snapshots_still_returns_header(self):
        with patched_board(board_patches()):
            board = format_market_board([])
        self.assertIn("USD / IQD", board)
        self.assertNotIn("Source: 0 market observations", board)  # no summary when no rates

    def test_board_shows_current_spread_line(self):
        snaps = [make_snapshot(city="erbil", median_rate=152900, consensus_rate=152900),
                 make_snapshot(city="baghdad", median_rate=154000, consensus_rate=154000)]
        with patched_board(board_patches()):
            board = format_market_board(snaps)
        self.assertIn("152,900 — 154,000", board)  # ئێستا current spread across cities

    def test_board_shows_todays_true_high_low(self):
        now = datetime.now(timezone.utc)
        history = [
            {"rate": 154700, "recorded_at": (now - timedelta(minutes=5)).isoformat()},
            {"rate": 154050, "recorded_at": (now - timedelta(hours=6)).isoformat()},
        ]
        snaps = [make_snapshot(city="erbil", median_rate=152900, consensus_rate=152900),
                 make_snapshot(city="baghdad", median_rate=154000, consensus_rate=154000)]
        with patched_board(board_patches(get_rate_history_all=history)):
            board = format_market_board(snaps)
        # True day extremes from history, not the current city spread.
        self.assertIn("بەرزترین ئەمڕۆ: 154,700", board)
        self.assertIn("نزمترین ئەمڕۆ: 154,050", board)

    def test_board_skips_day_lines_without_history(self):
        snaps = [make_snapshot(city="erbil", median_rate=152900, consensus_rate=152900)]
        with patched_board(board_patches()):
            board = format_market_board(snaps)
        self.assertNotIn("بەرزترین ئەمڕۆ", board)
        self.assertIn("152,900 — 152,900", board)  # current spread still shown


class TestDayRateStats(unittest.TestCase):
    def test_open_close_high_low(self):
        now = datetime.now(timezone.utc)
        rows = [
            {"rate": 154700, "recorded_at": (now - timedelta(minutes=5)).isoformat()},   # newest = close
            {"rate": 154250, "recorded_at": (now - timedelta(hours=6)).isoformat()},     # morning
            {"rate": 154050, "recorded_at": (now - timedelta(hours=11)).isoformat()},    # earliest today = open
        ]
        with patch("output.formatter.db.get_rate_history_all", return_value=rows):
            stats = day_rate_stats()
        self.assertEqual(stats["open"], 154050)
        self.assertEqual(stats["close"], 154700)
        self.assertEqual(stats["high"], 154700)
        self.assertEqual(stats["low"], 154050)

    def test_yesterday_rows_excluded(self):
        # 30h ago is the previous Baghdad day (day boundary is 21:00 UTC) and
        # must not leak into today's high/low.
        now = datetime.now(timezone.utc)
        rows = [
            {"rate": 154700, "recorded_at": (now - timedelta(minutes=5)).isoformat()},
            {"rate": 153000, "recorded_at": (now - timedelta(hours=30)).isoformat()},
        ]
        with patch("output.formatter.db.get_rate_history_all", return_value=rows):
            stats = day_rate_stats()
        self.assertEqual(stats["low"], 154700)  # 153,000 from yesterday ignored
        self.assertEqual(stats["high"], 154700)

    def test_no_history_returns_none(self):
        with patch("output.formatter.db.get_rate_history_all", return_value=[]):
            self.assertIsNone(day_rate_stats())

    def test_only_yesterday_returns_none(self):
        now = datetime.now(timezone.utc)
        rows = [{"rate": 154050, "recorded_at": (now - timedelta(hours=30)).isoformat()}]
        with patch("output.formatter.db.get_rate_history_all", return_value=rows):
            self.assertIsNone(day_rate_stats())


if __name__ == "__main__":
    unittest.main()
