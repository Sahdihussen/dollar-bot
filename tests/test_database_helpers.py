import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import database as db


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    """Minimal chainable stand-in for supabase-py's query builder."""

    def __init__(self, client, table):
        self._client = client
        self._table = table
        self._ops = []

    def _rec(self, op, *args, **kwargs):
        self._ops.append((op, args, kwargs))
        return self

    def select(self, *cols):
        return self._rec("select", *cols)

    def eq(self, col, val):
        return self._rec("eq", col, val)

    def gte(self, col, val):
        return self._rec("gte", col, val)

    def order(self, col, **kwargs):
        return self._rec("order", col, **kwargs)

    def limit(self, n):
        return self._rec("limit", n)

    def update(self, payload):
        return self._rec("update", payload)

    def insert(self, payload):
        return self._rec("insert", payload)

    def execute(self):
        self._client.calls.append((self._table, list(self._ops)))
        return FakeResult(self._client.data.get(self._table, []))


class FakeClient:
    def __init__(self, data=None):
        self.data = data or {}
        self.calls = []

    def table(self, name):
        return FakeQuery(self, name)


class TestRateHistoryWindow(unittest.TestCase):
    """Regression test: get_rate_history must actually filter by minutes."""

    def test_query_includes_gte_window(self):
        client = FakeClient({
            "rate_history": [{"city": "baghdad", "rate": 154000, "recorded_at": "2026-08-24T13:00:00+00:00"}],
        })
        with patch("database.get_client", return_value=client):
            rows = db.get_rate_history("baghdad", minutes=30)

        self.assertEqual(len(rows), 1)
        table, ops = client.calls[0]
        self.assertEqual(table, "rate_history")
        op_names = [op[0] for op in ops]
        # The window filter must be applied (this was silently dropped before).
        self.assertIn("gte", op_names)
        gte = next(op for op in ops if op[0] == "gte")
        self.assertEqual(gte[1][0], "recorded_at")
        # Cutoff is ~30 minutes before now.
        cutoff = datetime.fromisoformat(gte[1][1])
        age = datetime.now(timezone.utc) - cutoff
        self.assertGreaterEqual(age, timedelta(minutes=29))
        self.assertLessEqual(age, timedelta(minutes=31))
        # Newest first.
        order = next(op for op in ops if op[0] == "order")
        self.assertEqual(order[1][0], "recorded_at")
        self.assertEqual(order[2], {"desc": True})

    def test_minutes_zero_still_filters(self):
        client = FakeClient({"rate_history": []})
        with patch("database.get_client", return_value=client):
            db.get_rate_history("erbil", minutes=0)
        _, ops = client.calls[0]
        self.assertIn("gte", [op[0] for op in ops])


class TestPendingActions(unittest.TestCase):
    def test_get_pending_actions_filters_and_orders_oldest_first(self):
        client = FakeClient({
            "pending_actions": [{"id": 3, "action": "publish_board", "status": "pending"}],
        })
        with patch("database.get_client", return_value=client):
            rows = db.get_pending_actions(limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 3)
        _, ops = client.calls[0]
        eq = next(op for op in ops if op[0] == "eq")
        self.assertEqual(eq[1], ("status", "pending"))
        order = next(op for op in ops if op[0] == "order")
        self.assertEqual(order[1][0], "created_at")
        self.assertEqual(order[2], {"desc": False})  # oldest first

    def test_mark_pending_action_sends_status_and_timestamp(self):
        client = FakeClient()
        with patch("database.get_client", return_value=client):
            db.mark_pending_action(7, status="failed", error="boom")

        table, ops = client.calls[0]
        self.assertEqual(table, "pending_actions")
        update = next(op for op in ops if op[0] == "update")
        payload = update[1][0]
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["error"], "boom")
        self.assertIn("processed_at", payload)
        eq = next(op for op in ops if op[0] == "eq")
        self.assertEqual(eq[1], ("id", 7))

    def test_mark_pending_action_error_truncated(self):
        client = FakeClient()
        with patch("database.get_client", return_value=client):
            db.mark_pending_action(1, status="failed", error="x" * 600)
        _, ops = client.calls[0]
        update = next(op for op in ops if op[0] == "update")
        self.assertEqual(len(update[1][0]["error"]), 500)


class TestFreshSnapshots(unittest.TestCase):
    def _ts(self, minutes_ago: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()

    def test_only_fresh_cities_returned(self):
        rows = [
            {"city": "erbil", "freshest_at": self._ts(5)},
            {"city": "baghdad", "freshest_at": self._ts(300)},   # stale
            {"city": "duhok", "freshest_at": self._ts(1)},
        ]
        with patch("database.get_all_latest_snapshots", return_value=rows):
            fresh = db.get_fresh_snapshots(max_age_minutes=120)
        self.assertEqual([r["city"] for r in fresh], ["erbil", "duhok"])

    def test_falls_back_to_snapshot_at_when_freshest_missing(self):
        rows = [
            {"city": "mosul", "snapshot_at": self._ts(10)},       # fresh via fallback
            {"city": "basra", "snapshot_at": self._ts(200)},      # stale
        ]
        with patch("database.get_all_latest_snapshots", return_value=rows):
            fresh = db.get_fresh_snapshots(max_age_minutes=120)
        self.assertEqual([r["city"] for r in fresh], ["mosul"])

    def test_missing_timestamps_are_stale(self):
        rows = [{"city": "kirkuk"}]
        with patch("database.get_all_latest_snapshots", return_value=rows):
            fresh = db.get_fresh_snapshots()
        self.assertEqual(fresh, [])

    def test_empty_history_returns_empty(self):
        with patch("database.get_all_latest_snapshots", return_value=[]):
            self.assertEqual(db.get_fresh_snapshots(), [])


if __name__ == "__main__":
    unittest.main()
