"""Regression checks for paper-only cost gate without Kraken access."""
import unittest
from pathlib import Path

SOURCE=Path("research/isolated_paper_experiment.py").read_text()

class PaperCostGateTests(unittest.TestCase):
    def test_recent_range_requires_buffer(self):
        self.assertIn('report["estimated_roundtrip_cost_pct"]*1.25',SOURCE)
        self.assertIn('and cost_ok and volume_ok',SOURCE)

    def test_net_target_accounts_for_execution_and_fees(self):
        self.assertIn('target_fill=target*(1-SLIP) if direction=="LONG" else target*(1+SLIP)',SOURCE)
        self.assertIn('reward_net=gross_target-(entry+target_fill)*FEE',SOURCE)
        self.assertIn('reward_net>=2*unit_risk',SOURCE)

    def test_no_real_orders(self):
        self.assertIn('orders_enabled"]',SOURCE)
        self.assertIn('"orders_enabled":False',SOURCE)

if __name__=="__main__":
    unittest.main()
