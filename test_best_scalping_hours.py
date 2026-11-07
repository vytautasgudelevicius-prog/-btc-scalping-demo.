import unittest
from research.best_scalping_hours import run,stats

class HourResearchTests(unittest.TestCase):
    def test_empty_returns(self):
        self.assertEqual(stats([])["trades"],0)
        self.assertIsNone(stats([])["avg_net_pct"])
    def test_net_returns(self):
        self.assertAlmostEqual(stats([.01,-.005])["avg_net_pct"],.25)
    def test_no_history_fails_closed(self):
        with self.assertRaises(ValueError):
            run([])
    def test_negative_fees_rejected(self):
        with self.assertRaises(ValueError):
            run([],fee_per_side=-.01)

if __name__=="__main__":
    unittest.main()
