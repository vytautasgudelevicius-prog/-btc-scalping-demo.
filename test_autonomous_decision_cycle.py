import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from research.autonomous_decision_cycle import assess

ROWS=[(datetime(2026,1,1,tzinfo=timezone.utc),)]

class DecisionCycleTests(unittest.TestCase):
    def test_empty_history_fails_closed(self):
        with self.assertRaises(ValueError):
            assess([])
    @patch("research.autonomous_decision_cycle.hourly")
    @patch("research.autonomous_decision_cycle.walk_forward")
    def test_losses_never_authorize_orders(self,wf,hour):
        wf.return_value={"decision":"NO_TRADE","folds":[{"decision":"NO_TRADE","test":{"trades":30,"avg_net_pct":-1.0}}]}
        hour.return_value={"decision":"RESEARCH_ONLY","selected_utc_hours":[8,9],"untouched_test":{"trades":40,"avg_net_pct":2.0}}
        r=assess(ROWS)
        self.assertEqual(r["decision"],"NO_TRADE")
        self.assertFalse(r["demo_trade"]["orders_enabled"])
        self.assertFalse(r["signal_confirmation"]["fixed_hour_trading_filter"])
    @patch("research.autonomous_decision_cycle.hourly")
    @patch("research.autonomous_decision_cycle.walk_forward")
    def test_positive_history_still_requires_forward_paper(self,wf,hour):
        wf.return_value={"decision":"RESEARCH_ONLY","folds":[{"decision":"RESEARCH_ONLY","test":{"trades":31,"avg_net_pct":0.2}}]}
        hour.return_value={"decision":"NO_TRADE","selected_utc_hours":[]}
        r=assess(ROWS)
        self.assertEqual(r["decision"],"SHADOW_RESEARCH_ONLY")
        self.assertFalse(r["signal_confirmation"]["historical_edge_verified"])
        self.assertFalse(r["demo_trade"]["orders_enabled"])
        self.assertTrue(r["strategy_improvement"]["candidate_for_forward_shadow_monitoring"])
if __name__=="__main__":
    unittest.main()
