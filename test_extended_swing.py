"""Fail-closed safety checks for extended BTC research, not trading orders."""
import unittest
from datetime import datetime,timedelta,timezone
from research.extended_swing_edge import run

def bars(n=120000):
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    return [(start+timedelta(minutes=i),100.,100.,100.,100.,1.) for i in range(n)]

class ExtendedSwingSafetyTests(unittest.TestCase):
    def test_flat_history_never_promotes(self):
        result=run(bars())
        self.assertEqual(result["decision"],"NO_TRADE")
        self.assertIsNone(result["selected_on_validation"])
        self.assertIsNone(result["untouched_test"])

    def test_noncontiguous_history_rejected(self):
        history=bars()
        del history[500]
        with self.assertRaisesRegex(ValueError,"Noncontiguous"):
            run(history)

    def test_negative_costs_rejected(self):
        with self.assertRaisesRegex(ValueError,"Negative"):
            run(bars(),fee_per_side=-.001)

if __name__=="__main__":
    unittest.main()
