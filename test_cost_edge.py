import unittest
from research.evaluate_cost_edge import simulate

class ConstantModelTests(unittest.TestCase):
    def test_costs_are_deducted_from_correct_long(self):
        import research.evaluate_cost_edge as m
        original=m.predict
        try:
            m.predict=lambda model,x:.9
            result=simulate({},[([0],1)],[(0,.01)],.75,fee_per_side=.004,spread_bps=5,slippage_bps=2)
            self.assertEqual(result["trades"],1)
            self.assertAlmostEqual(result["avg_net_return_pct"],.11)
        finally:
            m.predict=original

    def test_no_trade_below_threshold(self):
        import research.evaluate_cost_edge as m
        original=m.predict
        try:
            m.predict=lambda model,x:.51
            result=simulate({},[([0],1)],[(0,.01)],.75)
            self.assertEqual(result["trades"],0)
            self.assertIsNone(result["avg_net_return_pct"])
        finally:
            m.predict=original

    def test_misaligned_labels_rejected(self):
        with self.assertRaises(ValueError):
            simulate({},[([0],1)],[],.5)

if __name__=="__main__":
    unittest.main()
