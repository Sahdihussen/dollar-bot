import unittest

from database import snapshot_is_fresh


class TestSnapshotIsFresh(unittest.TestCase):
    def test_recent_timestamp_is_fresh(self):
        cutoff = "2026-08-24T08:19:28.123456+00:00"
        self.assertTrue(snapshot_is_fresh("2026-08-24T10:07:18.49488+00:00", cutoff))

    def test_old_timestamp_is_stale(self):
        cutoff = "2026-08-24T10:19:28.123456+00:00"
        self.assertFalse(snapshot_is_fresh("2026-08-24T08:07:18.49488+00:00", cutoff))

    def test_boundary_second_counts_as_fresh(self):
        cutoff = "2026-08-24T10:19:28.999999+00:00"
        self.assertTrue(snapshot_is_fresh("2026-08-24T10:19:28.123+00:00", cutoff))
        self.assertFalse(snapshot_is_fresh("2026-08-24T10:19:27.999+00:00", cutoff))

    def test_variable_microsecond_widths_compare_ok(self):
        # Supabase returns both 5- and 6-digit microsecond widths
        cutoff = "2026-08-24T10:00:00.000000+00:00"
        self.assertTrue(snapshot_is_fresh("2026-08-24T10:30:00.49488+00:00", cutoff))
        self.assertTrue(snapshot_is_fresh("2026-08-24T10:30:00.494880+00:00", cutoff))

    def test_missing_timestamp_is_stale(self):
        self.assertFalse(snapshot_is_fresh(None, "2026-08-24T10:19:28+00:00"))
        self.assertFalse(snapshot_is_fresh("", "2026-08-24T10:19:28+00:00"))

    def test_no_fractional_seconds(self):
        cutoff = "2026-08-24T09:00:00+00:00"
        self.assertTrue(snapshot_is_fresh("2026-08-24T09:30:00+00:00", cutoff))
        self.assertFalse(snapshot_is_fresh("2026-08-24T08:30:00+00:00", cutoff))


if __name__ == "__main__":
    unittest.main()
