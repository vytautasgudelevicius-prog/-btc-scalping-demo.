"""Safety checks for trading curriculum; no orders."""
import datetime as dt
import unittest
from research.trading_curriculum import trading_lesson_report

def candles(n=240):
    start=dt.datetime(2026,1,1,tzinfo=dt.timezone.utc)
    return [(start+dt.timedelta(minutes=i),100.,100.2,99.8,100.,1.) for i in range(n)]

class CurriculumTests(unittest.TestCase):
    def test_no_history_waits(self):
        self.assertEqual(trading_lesson_report(candles(30))["decision"],"WAIT")

    def test_flat_market_waits(self):
        report=trading_lesson_report(candles())
        self.assertEqual(report["decision"],"WAIT")
        self.assertEqual(report["reason"],"insufficient_volume")

    def test_costs_can_invalidate_trade(self):
        report=trading_lesson_report(candles(),target_pct=.001)
        self.assertEqual(report["reason"],"costs_exceed_target")

    def test_gap_in_data_fails_closed(self):
        rows=candles()
        rows[-2]=(rows[-2][0]+dt.timedelta(minutes=2),*rows[-2][1:])
        self.assertEqual(trading_lesson_report(rows)["reason"],"missing_or_duplicate_minutes")

if __name__=="__main__":
    unittest.main()
