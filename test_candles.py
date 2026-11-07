"""Deterministic tests for research-only candle features."""
import datetime as dt
import unittest
from research.candles import aggregate, atr_pct, breakout, candle_features, engulfing, research_signal

UTC = dt.timezone.utc

def bar(i, o=100, h=102, l=98, c=101, v=2):
    return (dt.datetime(2026, 1, 1, tzinfo=UTC) + dt.timedelta(minutes=i), o, h, l, c, v)

class CandleResearchTests(unittest.TestCase):
    def test_wicks(self):
        f = candle_features(bar(0))
        self.assertAlmostEqual(f["body_ratio"], .25)
        self.assertAlmostEqual(f["upper_wick_ratio"], .25)
        self.assertAlmostEqual(f["lower_wick_ratio"], .5)

    def test_engulfing(self):
        self.assertEqual(engulfing(bar(0, 102, 103, 99, 100),
                                   bar(1, 99, 104, 98, 103)), "BULLISH")

    def test_completed_buckets_only(self):
        rows = [bar(i) for i in range(12)]
        self.assertEqual(len(aggregate(rows, 5)), 2)
        self.assertEqual(aggregate(rows, 5)[0][5], 10)

    def test_missing_minute_discards_bucket(self):
        rows = [bar(i) for i in range(10) if i != 2]
        self.assertEqual(len(aggregate(rows, 5)), 1)

    def test_breakout_no_lookahead(self):
        rows = [bar(i) for i in range(20)] + [bar(20, 101, 106, 100, 105)]
        self.assertEqual(breakout(rows), "UP")

    def test_atr(self):
        self.assertIsNotNone(atr_pct([bar(i) for i in range(15)]))

    def test_wait_without_history(self):
        self.assertEqual(research_signal([bar(i) for i in range(30)])["signal"], "WAIT")

if __name__ == "__main__":
    unittest.main()
