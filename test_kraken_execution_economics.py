"""Safety and arithmetic checks for BTC/EUR spot execution economics."""
import unittest
from research.kraken_execution_economics import required_gross_move,analyze

class KrakenExecutionEconomicsTests(unittest.TestCase):
    def test_zero_costs_need_zero_move(self):
        self.assertEqual(required_gross_move(0,0,0,0),0)
    def test_fee_only_exact_break_even(self):
        fee=.008
        actual=required_gross_move(fee,fee,0,0)
        self.assertAlmostEqual(actual,(1+fee)/(1-fee)-1)
    def test_spread_and_slippage_increase_threshold(self):
        baseline=required_gross_move(.008,.008,0,0)
        self.assertGreater(required_gross_move(.008,.008,5,2),baseline)
    def test_maker_assumption_lowers_threshold(self):
        result=analyze()["scenarios"]
        self.assertLess(result["tier1_maker_maker"]["break_even_gross_move_pct"],
                        result["tier1_taker_taker"]["break_even_gross_move_pct"])
    def test_negative_costs_fail_closed(self):
        with self.assertRaises(ValueError):
            required_gross_move(-.001,.008)
    def test_invalid_fee_fails_closed(self):
        with self.assertRaises(ValueError):
            required_gross_move(.008,1.0)

if __name__=="__main__":
    unittest.main()
