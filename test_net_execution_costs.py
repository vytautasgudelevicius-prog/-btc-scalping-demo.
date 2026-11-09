import unittest
from research.net_execution_costs import net_execution, compare_cost_scenarios

class NetExecutionTests(unittest.TestCase):
    def test_flat_long_loses_costs(self):
        result = net_execution("LONG", 1, 100, 100, fee_per_side=.008)
        self.assertLess(result["net_pnl_eur"], 0)

    def test_flat_short_loses_costs(self):
        result = net_execution("SHORT", 1, 100, 100, fee_per_side=.008)
        self.assertLess(result["net_pnl_eur"], 0)

    def test_low_fee_scenario_is_not_claimed_as_kraken(self):
        result = compare_cost_scenarios("LONG", 1, 100, 101)
        self.assertGreater(result["hypothetical_0_05pct_each_side"]["net_pnl_eur"],
                           result["conservative_0_8pct_each_side"]["net_pnl_eur"])

    def test_fees_on_both_fills(self):
        result = net_execution("LONG", 2, 100, 101, fee_per_side=.008)
        self.assertAlmostEqual(result["entry_fee_eur"], result["entry_fill"]*2*.008)
        self.assertAlmostEqual(result["exit_fee_eur"], result["exit_fill"]*2*.008)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            net_execution("LONG", 0, 100, 101, fee_per_side=.008)

if __name__ == "__main__":
    unittest.main()
