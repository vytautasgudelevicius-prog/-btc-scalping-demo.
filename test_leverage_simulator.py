import unittest
from research.leverage_simulator import LeverageTrade, simulate

class LeverageSimulatorTests(unittest.TestCase):
    def test_long_profit_grows_with_leverage_before_costs(self):
        a=simulate(LeverageTrade(1,100,101,2,100,fee_per_side=0,spread_bps=0,slippage_bps=0))
        b=simulate(LeverageTrade(1,100,101,5,100,fee_per_side=0,spread_bps=0,slippage_bps=0))
        self.assertGreater(b["net_pnl_eur"],a["net_pnl_eur"])

    def test_short_profit(self):
        r=simulate(LeverageTrade(-1,100,99,3,100,fee_per_side=0,spread_bps=0,slippage_bps=0))
        self.assertGreater(r["net_pnl_eur"],0)

    def test_long_liquidation_from_intrabar_low(self):
        r=simulate(LeverageTrade(1,100,101,5,100,adverse_extreme=70))
        self.assertTrue(r["liquidated"])
        self.assertEqual(r["ending_margin_eur"],0)

    def test_short_liquidation_from_intrabar_high(self):
        r=simulate(LeverageTrade(-1,100,99,5,100,adverse_extreme=130))
        self.assertTrue(r["liquidated"])

    def test_costs_reduce_profit(self):
        a=simulate(LeverageTrade(1,100,101,3,100,fee_per_side=0,spread_bps=0,slippage_bps=0))
        b=simulate(LeverageTrade(1,100,101,3,100))
        self.assertLess(b["net_pnl_eur"],a["net_pnl_eur"])

    def test_invalid_side_and_excess_leverage(self):
        with self.assertRaises(ValueError):simulate(LeverageTrade(0,100,101,2,100))
        with self.assertRaises(ValueError):simulate(LeverageTrade(1,100,101,50,100))

if __name__=="__main__":unittest.main()
