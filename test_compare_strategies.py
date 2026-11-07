import unittest
from datetime import datetime,timedelta,timezone
from research.compare_strategies import compare,signals

class StrategyComparisonTests(unittest.TestCase):
    def test_no_lookahead_in_signals(self):
        base=[(None,100,101,99,100,10)]*25
        a=signals(base,24)
        b=signals(base+[(None,100,200,1,150,10)],24)
        self.assertEqual(a,b)

    def test_insufficient_history_rejected(self):
        with self.assertRaises(ValueError):
            compare([])

    def test_flat_market_has_no_positive_edge_after_costs(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[(start+timedelta(minutes=i),100,100,100,100,10) for i in range(3000)]
        r=compare(rows)
        self.assertEqual(r["decision"],"NO_TRADE")
        self.assertEqual(r["strategies"]["trend"]["trades"],0)

    def test_gaps_rejected(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[(start,100,100,100,100,1),(start+timedelta(minutes=2),100,100,100,100,1)]
        with self.assertRaises(ValueError):
            compare(rows)

if __name__=="__main__":
    unittest.main()
