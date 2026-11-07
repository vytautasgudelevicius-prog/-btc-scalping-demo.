"""Regression tests for the undefined 'gross' shadow settlement failure."""
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from research.kraken_shadow_forward import initialize, record, settle, net_return


class TestShadowSettlementGross(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize(self.db)
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def tearDown(self):
        self.db.close()

    def report(self, when, direction="LONG", bid=100.0, ask=100.1):
        return {
            "last_completed_candle": self.start.isoformat(),
            "timestamp_utc": when.isoformat(),
            "ema_signal": direction,
            "bid": bid, "ask": ask, "spread_pct": 0.1,
            "estimated_roundtrip_cost_pct": 1.74,
            "quality_filter": True, "liquidity_atr_filter": True,
            "context_candidate": True
        }

    def test_five_minute_settlement_has_defined_gross_and_net(self):
        record(self.db, self.report(self.start))
        result = settle(self.db, self.report(self.start + timedelta(minutes=5), bid=102, ask=102.1))
        self.assertEqual(result, 1)
        gross, net = self.db.execute("SELECT gross_pct,net_pct FROM observations").fetchone()
        self.assertIsInstance(gross, float)
        self.assertIsInstance(net, float)
        self.assertGreater(gross, net)

    def test_late_quote_does_not_count_as_five_minute_fill(self):
        record(self.db, self.report(self.start))
        self.assertEqual(settle(self.db, self.report(self.start + timedelta(minutes=8))), 0)
        self.assertIsNone(self.db.execute("SELECT gross_pct FROM observations").fetchone()[0])

    def test_short_gross_is_defined(self):
        gross, net = net_return("SHORT", 100, 100.1, 99, 99.1)
        self.assertIsInstance(gross, float)
        self.assertGreater(gross, net)


if __name__ == "__main__":
    unittest.main()
